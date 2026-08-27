"""Strongly-typed LangGraph agent state.

All fields are explicit — no raw dict-based state.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class InvestigationStatus(str, Enum):
    PENDING = "PENDING"
    INVESTIGATING = "INVESTIGATING"
    ANALYZED = "ANALYZED"
    REMEDIATION_PLANNED = "REMEDIATION_PLANNED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    REMEDIATION_APPROVED = "REMEDIATION_APPROVED"
    REMEDIATION_REJECTED = "REMEDIATION_REJECTED"
    REMEDIATING = "REMEDIATING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NOT_REQUIRED = "NOT_REQUIRED"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class EvidenceItem(BaseModel):
    """A single piece of collected evidence."""

    source: str
    resource: str
    observation: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_reference: Optional[str] = None
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    is_inference: bool = False


class ToolResult(BaseModel):
    """Structured output from any infrastructure tool."""

    tool_name: str
    status: str
    command_type: str
    resource: Optional[str] = None
    namespace: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    exit_code: Optional[int] = None
    duration: Optional[float] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None
    raw_output: Optional[Any] = None


class InvestigationStep(BaseModel):
    """A single planned or executed investigation step."""

    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str
    tool: Optional[str] = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    status: str = "PENDING"
    result: Optional[ToolResult] = None


class InvestigationPlan(BaseModel):
    """The LLM-generated investigation plan."""

    summary: str
    steps: List[InvestigationStep] = Field(default_factory=list)
    estimated_tools: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RootCauseAnalysis(BaseModel):
    """Structured root cause analysis output."""

    incident_status: str
    affected_resource: str
    root_cause: str
    confidence: ConfidenceLevel
    evidence_references: List[str] = Field(default_factory=list)
    reasoning_summary: str
    alternative_causes: List[str] = Field(default_factory=list)
    recommended_next_investigation: List[str] = Field(default_factory=list)
    risk: RiskLevel = RiskLevel.MEDIUM


class RemediationAction(BaseModel):
    """A single remediation recommendation."""

    remediation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action: str
    reason: str
    expected_result: str
    risk: RiskLevel
    rollback: str
    approval_required: bool = True
    tool: Optional[str] = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class RemediationPlan(BaseModel):
    """Collection of remediation recommendations requiring approval."""

    actions: List[RemediationAction] = Field(default_factory=list)
    overall_risk: RiskLevel = RiskLevel.MEDIUM
    requires_approval: bool = True


class ApprovalRecord(BaseModel):
    """Human approval decision record."""

    approval_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    approver: Optional[str] = None
    approved_action_ids: List[str] = Field(default_factory=list)
    rejected_action_ids: List[str] = Field(default_factory=list)
    reason: Optional[str] = None
    timestamp: Optional[datetime] = None


class RemediationResult(BaseModel):
    """Result of an executed remediation action."""

    request_id: str
    action_id: str
    approval_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approver: Optional[str] = None
    tool: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    result: Optional[str] = None
    exit_code: Optional[int] = None
    verification_status: str = "NOT_VERIFIED"
    success: bool = False


class VerificationResult(BaseModel):
    """Post-remediation infrastructure verification."""

    verified: bool
    status: str
    before_state: Optional[str] = None
    after_state: Optional[str] = None
    details: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FinalReport(BaseModel):
    """Complete incident investigation and remediation report."""

    request_id: str
    user_request: str
    investigation_summary: str
    root_cause: Optional[RootCauseAnalysis] = None
    evidence_count: int = 0
    issues_found: List[str] = Field(default_factory=list)
    remediation_plan: Optional[RemediationPlan] = None
    remediation_results: List[RemediationResult] = Field(default_factory=list)
    verification: Optional[VerificationResult] = None
    overall_status: InvestigationStatus = InvestigationStatus.COMPLETED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    errors: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Primary agent state
# ---------------------------------------------------------------------------


class AgentState(BaseModel):
    """Complete typed state for the LangGraph workflow.

    This is the single source of truth passed between all graph nodes.
    No raw dicts — every field is typed and validated.
    """

    # Identity
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_request: str

    # Workflow position
    status: InvestigationStatus = InvestigationStatus.PENDING
    current_step: int = 0

    # Planning
    investigation_plan: Optional[InvestigationPlan] = None

    # Execution results
    tool_results: List[ToolResult] = Field(default_factory=list)
    evidence: List[EvidenceItem] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)

    # Analysis
    root_cause: Optional[RootCauseAnalysis] = None
    confidence: ConfidenceLevel = ConfidenceLevel.INSUFFICIENT

    # Remediation
    remediation_plan: Optional[RemediationPlan] = None
    risk: RiskLevel = RiskLevel.MEDIUM

    # Approval
    approval_required: bool = True
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    approval_record: Optional[ApprovalRecord] = None

    # Execution & Verification
    remediation_result: Optional[RemediationResult] = None
    verification_result: Optional[VerificationResult] = None

    # Final output
    final_report: Optional[FinalReport] = None

    # Error tracking
    errors: List[str] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
