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

    # Phase 1: return stub — full workflow wired in Phase 2
    return TroubleshootResponse(
        request_id=request_id,
        status="PENDING",
        approval_required=settings.require_human_approval,
        approval_status="PENDING",
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
