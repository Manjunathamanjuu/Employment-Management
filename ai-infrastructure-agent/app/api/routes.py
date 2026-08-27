"""FastAPI route definitions."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.api.models import (
    ApprovalRequest,
    HealthResponse,
    ReadyResponse,
    TroubleshootRequest,
    TroubleshootResponse,
)
from app.config import settings
from app.logging.logger import get_logger

logger = get_logger("ai_agent.api")

router = APIRouter()


# ---------------------------------------------------------------------------
# Health & Readiness
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    tags=["observability"],
)
async def health() -> HealthResponse:
    """Returns 200 when the service process is alive."""
    return HealthResponse(version=settings.app_version)


@router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Readiness probe",
    tags=["observability"],
)
async def ready() -> ReadyResponse:
    """Returns 200 when the service is ready to serve traffic."""
    checks: dict = {
        "config": "ok",
        "openai_key_configured": settings.openai_api_key_configured,
    }
    is_ready = settings.openai_api_key_configured

    if not is_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ReadyResponse(
                ready=False,
                checks=checks,
            ).model_dump(mode="json"),
        )

    return ReadyResponse(ready=True, checks=checks)


# ---------------------------------------------------------------------------
# Troubleshooting API
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/troubleshoot",
    response_model=TroubleshootResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit an infrastructure troubleshooting request",
    tags=["agent"],
)
async def troubleshoot(
    body: TroubleshootRequest,
    request: Request,
) -> TroubleshootResponse:
    """Accept a troubleshooting request and begin the investigation workflow.

    The response includes a request_id for polling the result.
    Full LangGraph workflow is wired in Phase 2.
    """
    request_id = str(uuid.uuid4())
    logger.info(
        "Troubleshooting request received",
        extra={
            "request_id": request_id,
            "agent_node": "api",
            "status": "received",
        },
    )

    # Prompt injection and privilege escalation check
    from app.security import detect_prompt_injection, detect_privilege_escalation, sanitise_llm_input
    is_injection, _ = detect_prompt_injection(body.request)
    if is_injection or detect_privilege_escalation(body.request):
        logger.warning(
            "Prompt injection or privilege escalation attempt blocked",
            extra={"request_id": request_id, "agent_node": "api", "status": "blocked"},
        )
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail={"error": "Request contains disallowed patterns", "code": "BLOCKED_INPUT"},
        )

    safe_request = sanitise_llm_input(body.request)

    try:
        from app.agent.graph import run_investigation
        from app.api.models import EvidenceItemResponse, RemediationActionResponse, RootCauseResponse

        final_state = run_investigation(
            user_request=safe_request,
            request_id=request_id,
        )

        root_cause_resp = None
        if final_state.root_cause:
            rca = final_state.root_cause
            root_cause_resp = RootCauseResponse(
                incident_status=rca.incident_status,
                affected_resource=rca.affected_resource,
                root_cause=rca.root_cause,
                confidence=rca.confidence.value,
                reasoning_summary=rca.reasoning_summary,
                alternative_causes=rca.alternative_causes,
                recommended_next_investigation=rca.recommended_next_investigation,
                risk=rca.risk.value,
            )

        evidence_resp = [
            EvidenceItemResponse(
                source=e.source,
                resource=e.resource,
                observation=e.observation,
                confidence=e.confidence.value,
                is_inference=e.is_inference,
            )
            for e in final_state.evidence
        ]

        remediation_resp = []
        if final_state.remediation_plan:
            remediation_resp = [
                RemediationActionResponse(
                    remediation_id=a.remediation_id,
                    action=a.action,
                    reason=a.reason,
                    expected_result=a.expected_result,
                    risk=a.risk.value,
                    rollback=a.rollback,
                    approval_required=a.approval_required,
                )
                for a in final_state.remediation_plan.actions
            ]

        return TroubleshootResponse(
            request_id=final_state.request_id,
            status=final_state.status.value,
            root_cause=root_cause_resp,
            confidence=final_state.confidence.value,
            evidence=evidence_resp,
            issues=final_state.issues,
            remediation=remediation_resp,
            approval_required=final_state.approval_required,
            approval_status=final_state.approval_status.value,
            errors=final_state.errors,
        )

    except Exception as exc:
        logger.error(
            "Investigation workflow failed",
            extra={
                "request_id": request_id,
                "agent_node": "api",
                "status": "error",
                "error_type": type(exc).__name__,
            },
        )
        return TroubleshootResponse(
            request_id=request_id,
            status="FAILED",
            approval_required=settings.require_human_approval,
            approval_status="PENDING",
            errors=["Investigation workflow encountered an internal error."],
        )


@router.post(
    "/api/v1/approve",
    response_model=dict,
    summary="Submit a human approval decision for a remediation plan",
    tags=["agent"],
)
async def approve(body: ApprovalRequest, request: Request) -> dict:
    """Record a human approval or rejection for a planned remediation.

    Rules enforced:
    - Approver must be a named, non-anonymous human.
    - Only PENDING approvals can be decided.
    - Decisions are final (REJECTED cannot become APPROVED).
    - APPROVED records unlock the remediation executor.
    """
    from app.approval.service import ApprovalError, get_approval_service

    log_extra = {
        "request_id": body.request_id,
        "agent_node": "api.approve",
        "status": "received",
    }
    logger.info("Approval decision received", extra=log_extra)

    service = get_approval_service()

    # Ensure a pending record exists (create if missing — idempotent)
    try:
        service.create_pending(body.request_id)
    except ApprovalError:
        pass  # Record already exists — that's fine

    try:
        record = service.submit_decision(
            request_id=body.request_id,
            approved=body.approved,
            approver=body.approver,
            reason=body.reason,
            approved_action_ids=body.approved_action_ids or None,
        )
        logger.info(
            f"Approval decision recorded: {record.status.value}",
            extra={
                "request_id": body.request_id,
                "agent_node": "api.approve",
                "status": record.status.value.lower(),
            },
        )
        return {
            "request_id": body.request_id,
            "approval_id": record.approval_id,
            "status": record.status.value,
            "approved": body.approved,
            "approver": body.approver,
            "timestamp": record.timestamp.isoformat() if record.timestamp else None,
        }
    except ApprovalError as exc:
        logger.warning(
            f"Approval error: {exc}",
            extra={
                "request_id": body.request_id,
                "agent_node": "api.approve",
                "status": "error",
            },
        )
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail={"error": str(exc), "code": "APPROVAL_ERROR"},
        )
