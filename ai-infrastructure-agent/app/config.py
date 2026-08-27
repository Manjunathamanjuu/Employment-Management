"""Application configuration loaded exclusively from environment variables."""

from __future__ import annotations

import os
from enum import Enum
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """Application settings — never hard-code secrets."""

    # Application
    app_name: str = "AI Infrastructure Troubleshooting Agent"
    app_version: str = "1.0.0"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    # Logging
    log_level: LogLevel = LogLevel.INFO
    log_format: str = "json"

    # OpenAI — REQUIRED at runtime, no default to avoid accidental blank usage
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")

    # GCP
    gcp_project_id: str = Field(default="gcp-dev-july-2026", alias="GCP_PROJECT_ID")
    gke_cluster_name: str = Field(
        default="employment-management-gke", alias="GKE_CLUSTER_NAME"
    )
    gke_region: str = Field(default="us-central1", alias="GKE_REGION")

    # Kubernetes
    kubernetes_namespace: str = Field(
        default="employment-management", alias="KUBERNETES_NAMESPACE"
    )
    kubernetes_context: Optional[str] = Field(
        default=None, alias="KUBERNETES_CONTEXT"
    )

    # Tool timeouts (seconds)
    tool_timeout_seconds: int = Field(default=30, alias="TOOL_TIMEOUT_SECONDS")
    llm_timeout_seconds: int = Field(default=60, alias="LLM_TIMEOUT_SECONDS")

    # Agent
    max_investigation_steps: int = Field(
        default=20, alias="MAX_INVESTIGATION_STEPS"
    )
    require_human_approval: bool = Field(
        default=True, alias="REQUIRE_HUMAN_APPROVAL"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name": True,
        "case_sensitive": False,
        "extra": "ignore",
    }

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def openai_key_must_not_be_example(cls, v: Optional[str]) -> Optional[str]:
        """Reject placeholder key values that would silently misconfigure the agent."""
        if v in (None, "", "your-openai-api-key-here", "sk-example"):
            return None
        return v

    @property
    def openai_api_key_configured(self) -> bool:
        """Return True only when a non-empty key is present."""
        return bool(self.openai_api_key)

    def redacted_dict(self) -> dict:
        """Return settings with secrets redacted for safe logging."""
        data = self.model_dump()
        secret_fields = {"openai_api_key"}
        for field in secret_fields:
            if data.get(field):
                data[field] = "[REDACTED]"
        return data


# Module-level singleton — callers import `settings`
settings = Settings()
