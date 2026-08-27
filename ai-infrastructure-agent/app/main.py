"""FastAPI application entry point."""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.models import ErrorResponse
from app.api.routes import router
from app.config import settings
from app.logging.logger import configure_logging, get_logger
from app.security import SecurityMiddleware

configure_logging(settings.log_level.value)
logger = get_logger("ai_agent.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    logger.info(
        "AI Infrastructure Troubleshooting Agent starting",
        extra={
            "agent_node": "startup",
            "status": "starting",
        },
    )
    # Log config (secrets redacted)
    logger.info(
        "Configuration loaded",
        extra={"agent_node": "startup", "status": "configured"},
    )
    yield
    logger.info(
        "AI Infrastructure Troubleshooting Agent shutting down",
        extra={"agent_node": "shutdown", "status": "stopping"},
    )


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Production-grade AI agent for Kubernetes, Docker, GCP, "
        "and Terraform infrastructure troubleshooting."
    ),
    lifespan=lifespan,
    # Never expose internal details in production
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

app.add_middleware(SecurityMiddleware)

# CORS — allow frontend served from same host or local dev origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "null",  # file:// local open
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=False,
)

app.include_router(router)

# Serve CloudOps frontend — mounted AFTER API routes so API always wins
_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(_frontend_dir):
    app.mount(
        "/",
        StaticFiles(directory=_frontend_dir, html=True),
        name="cloudops-frontend",
    )


# ---------------------------------------------------------------------------
# Exception handlers — never leak stack traces to clients
# ---------------------------------------------------------------------------


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = str(uuid.uuid4())
    logger.warning(
        "Request validation error",
        extra={
            "request_id": request_id,
            "agent_node": "api",
            "status": "validation_error",
            "error_type": "RequestValidationError",
        },
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="Request validation failed",
            code="VALIDATION_ERROR",
            request_id=request_id,
        ).model_dump(mode="json"),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    request_id = str(uuid.uuid4())
    logger.error(
        "Unhandled exception",
        extra={
            "request_id": request_id,
            "agent_node": "api",
            "status": "error",
            "error_type": type(exc).__name__,
        },
    )
    # NEVER expose internal details to clients
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="An internal error occurred",
            code="INTERNAL_ERROR",
            request_id=request_id,
        ).model_dump(mode="json"),
    )
