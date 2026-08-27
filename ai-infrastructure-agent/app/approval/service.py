"""Human Approval Service.

Enforces the approval workflow gate:
  PENDING  → remediation blocked
  APPROVED → remediation may proceed (only approved action IDs)
  REJECTED → remediation permanently blocked

Safety guarantees:
- Remediation NEVER executes without an explicit APPROVED record.
- Approval records are immutable after decision (no status flip from REJECTED → APPROVED).
- Every approval decision is timestamped and attributed to an approver.
- Partial approvals are supported: only explicitly approved action IDs execute.
- Approval is scoped per request_id — one request, one approval record.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.agent.state import ApprovalRecord, ApprovalStatus, RemediationPlan
from app.logging.logger import get_logger

logger = get_logger("ai_agent.approval")

# Thread-safe in-memory approval store
# In production this would be a durable database
_approval_store: dict[str, ApprovalRecord] = {}
_store_lock = threading.Lock()


class ApprovalError(Exception):
    """Raised when an approval operation violates a safety constraint."""


class ApprovalService:
    """Manages the human approval lifecycle for remediation requests.

    The approval workflow:
    1. create_pending()   — called when a remediation plan is ready for review
    2. submit_decision()  — called by a human operator via the API
    3. is_approved()      — called by the executor before every remediation action
    4. get_record()       — called for audit trail queries
    """

    # ---------------------------------------------------------------------------
    # Create
    # ---------------------------------------------------------------------------

    def create_pending(
        self,
        request_id: str,
        plan: Optional[RemediationPlan] = None,
    ) -> ApprovalRecord:
        """Create a new PENDING approval record for a remediation plan.

        Raises ApprovalError if an approval already exists for this request_id.
        """
        if not request_id or not isinstance(request_id, str):
            raise ApprovalError("request_id must be a non-empty string")

        with _store_lock:
            if request_id in _approval_store:
                existing = _approval_store[request_id]
                if existing.status != ApprovalStatus.PENDING:
                    raise ApprovalError(
                        f"Approval for request {request_id!r} already decided: "
                        f"{existing.status.value}"
                    )
                return existing  # idempotent if still pending

            action_ids = []
            if plan:
                action_ids = [a.remediation_id for a in plan.actions]

            record = ApprovalRecord(
                approval_id=str(uuid.uuid4()),
                request_id=request_id,
                status=ApprovalStatus.PENDING,
                approved_action_ids=action_ids,
            )
            _approval_store[request_id] = record

        logger.info(
            f"Approval record created: PENDING for request={request_id}",
            extra={"request_id": request_id, "agent_node": "approval", "status": "pending"},
        )
        return record

    # ---------------------------------------------------------------------------
    # Decision
    # ---------------------------------------------------------------------------

    def submit_decision(
        self,
        request_id: str,
        approved: bool,
        approver: str,
        reason: Optional[str] = None,
        approved_action_ids: Optional[list[str]] = None,
    ) -> ApprovalRecord:
        """Record a human approval or rejection decision.

        Rules:
        - Only PENDING approvals can be decided.
        - Approver must be a non-empty, non-anonymous identifier.
        - REJECTED decisions are final — cannot be re-approved.
        - approved_action_ids, if provided, restricts which actions may execute.
        """
        if not request_id:
            raise ApprovalError("request_id is required")
        if not approver or not approver.strip():
            raise ApprovalError("approver must be identified — anonymous approval not permitted")
        if approver.strip().lower() in ("anonymous", "system", "auto", "automated"):
            raise ApprovalError(
                f"Approver identity '{approver}' is not permitted. "
                "Human approver identification is required."
            )

        with _store_lock:
            record = _approval_store.get(request_id)
            if record is None:
                raise ApprovalError(
                    f"No approval record found for request_id={request_id!r}. "
                    "Create a pending record first."
                )

            if record.status != ApprovalStatus.PENDING:
                raise ApprovalError(
                    f"Approval for request {request_id!r} is already in state "
                    f"{record.status.value}. Decisions are final and cannot be changed."
                )

            new_status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED

            updated = ApprovalRecord(
                approval_id=record.approval_id,
                request_id=request_id,
                status=new_status,
                approver=approver.strip(),
                approved_action_ids=(
                    approved_action_ids
                    if approved_action_ids is not None
                    else record.approved_action_ids
                ),
                rejected_action_ids=(
                    record.approved_action_ids if not approved else []
                ),
                reason=reason,
                timestamp=datetime.now(timezone.utc),
            )
            _approval_store[request_id] = updated

        logger.info(
            f"Approval decision: {new_status.value} by '{approver}' "
            f"for request={request_id}",
            extra={
                "request_id": request_id,
                "agent_node": "approval",
                "status": new_status.value.lower(),
            },
        )
        return updated

    # ---------------------------------------------------------------------------
    # Query
    # ---------------------------------------------------------------------------

    def is_approved(self, request_id: str) -> bool:
        """Return True only when there is an explicit APPROVED record.

        Fail closed: any non-APPROVED state returns False.
        """
        with _store_lock:
            record = _approval_store.get(request_id)
        return record is not None and record.status == ApprovalStatus.APPROVED

    def is_action_approved(self, request_id: str, action_id: str) -> bool:
        """Return True only when the specific action_id is approved for this request.

        Fail closed: if the action_id is not in approved_action_ids, returns False.
        """
        with _store_lock:
            record = _approval_store.get(request_id)
        if record is None or record.status != ApprovalStatus.APPROVED:
            return False
        return action_id in record.approved_action_ids

    def get_record(self, request_id: str) -> Optional[ApprovalRecord]:
        """Return the approval record for a request, or None if not found."""
        with _store_lock:
            return _approval_store.get(request_id)

    def get_status(self, request_id: str) -> ApprovalStatus:
        """Return the current approval status, defaulting to PENDING if not found."""
        with _store_lock:
            record = _approval_store.get(request_id)
        if record is None:
            return ApprovalStatus.PENDING
        return record.status

    # ---------------------------------------------------------------------------
    # Cleanup (for testing / TTL-based expiry in production)
    # ---------------------------------------------------------------------------

    def clear_record(self, request_id: str) -> None:
        """Remove an approval record. For testing and TTL expiry only."""
        with _store_lock:
            _approval_store.pop(request_id, None)

    @classmethod
    def reset_store(cls) -> None:
        """Reset the in-memory store. For testing only."""
        with _store_lock:
            _approval_store.clear()


# Module-level singleton
_approval_service = ApprovalService()


def get_approval_service() -> ApprovalService:
    """Return the singleton ApprovalService."""
    return _approval_service
