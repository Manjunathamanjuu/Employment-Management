"""FastAPI route definitions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.api.models import (
    ApprovalRequest,
    ErrorResponse,
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

    try:
        from app.agent.graph import run_investigation
        from app.api.models import EvidenceItemResponse, RemediationActionResponse, RootCauseResponse

        final_state = run_investigation(
            user_request=body.request,
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
    summary="Submit a human approval decision",
    tags=["agent"],
)
async def approve(body: ApprovalRequest) -> dict:
    """Accept a human approval (or rejection) for a planned remediation.

    Full approval workflow is wired in Phase 8.
    """
    return {
        "request_id": body.request_id,
        "status": "APPROVAL_RECORDED",
        "approved": body.approved,
    }
