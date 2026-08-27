"""Pydantic request/response models for the HTTP API.

These are the external contract — distinct from internal agent state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------


class TroubleshootRequest(BaseModel):
    """POST /api/v1/troubleshoot request body."""

    request: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural-language description of the infrastructure issue.",
    )
    namespace: Optional[str] = Field(
        default=None,
        max_length=253,
        description="Kubernetes namespace to investigate. Defaults to configured namespace.",
    )
    context: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Additional context about the incident.",
    )

    @field_validator("request", mode="before")
    @classmethod
    def request_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("request must not be blank")
        return v.strip()

    @field_validator("namespace", mode="before")
    @classmethod
    def validate_namespace(cls, v: Optional[str]) -> Optional[str]:
        """Reject namespace values containing shell-injection characters."""
        if v is None:
            return v
        v = v.strip()
        # Kubernetes namespace: lowercase alphanumeric and hyphens only
        import re
        if not re.match(r"^[a-z0-9][a-z0-9\-]{0,251}[a-z0-9]$|^[a-z0-9]$", v):
            raise ValueError(
                "namespace must be a valid Kubernetes namespace "
                "(lowercase alphanumeric and hyphens)"
            )
        return v


class ApprovalRequest(BaseModel):
    """POST /api/v1/approve request body."""

    request_id: str = Field(..., min_length=1, max_length=100)
    approved: bool
    approver: str = Field(..., min_length=1, max_length=200)
    reason: Optional[str] = Field(default=None, max_length=1000)
    approved_action_ids: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------


class EvidenceItemResponse(BaseModel):
    source: str
    resource: str
    observation: str
    confidence: str
    is_inference: bool = False


class RemediationActionResponse(BaseModel):
    remediation_id: str
    action: str
    reason: str
    expected_result: str
    risk: str
    rollback: str
    approval_required: bool


class RootCauseResponse(BaseModel):
    incident_status: str
    affected_resource: str
    root_cause: str
    confidence: str
    reasoning_summary: str
    alternative_causes: List[str] = Field(default_factory=list)
    recommended_next_investigation: List[str] = Field(default_factory=list)
    risk: str


class TroubleshootResponse(BaseModel):
    """POST /api/v1/troubleshoot response body."""

    request_id: str
    status: str
    root_cause: Optional[RootCauseResponse] = None
    confidence: str = "INSUFFICIENT"
    evidence: List[EvidenceItemResponse] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    remediation: List[RemediationActionResponse] = Field(default_factory=list)
    approval_required: bool = True
    approval_status: str = "PENDING"
    errors: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HealthResponse(BaseModel):
    """GET /health response body."""

    status: str = "ok"
    version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReadyResponse(BaseModel):
    """GET /ready response body."""

    ready: bool
    checks: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ErrorResponse(BaseModel):
    """Standard error response — never exposes internal stack traces."""

    error: str
    code: str
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
