"""Structured JSON logger.

Rules:
- Never log secrets, API keys, tokens, passwords, or credentials.
- Always include request_id, timestamp, agent_node, tool_name, execution_time, status.
- Output is JSON-formatted for log aggregation pipelines.
"""

from __future__ import annotations

import logging
import sys
import re
from typing import Any, Optional
import json
import time

# Patterns that indicate potentially sensitive content
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9\-_]{20,}", re.IGNORECASE),  # OpenAI keys
    re.compile(r"(?i)password\s*[:=]\s*\S+"),
    re.compile(r"(?i)token\s*[:=]\s*\S+"),
    re.compile(r"(?i)secret\s*[:=]\s*\S+"),
    re.compile(r"(?i)api[_-]?key\s*[:=]\s*\S+"),
    re.compile(r"(?i)private[_-]?key\s*[:=]\s*\S+"),
    re.compile(r"(?i)credentials?\s*[:=]\s*\S+"),
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),  # GCP API keys
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def _scrub_secrets(message: str) -> str:
    """Replace any detected secret patterns with [REDACTED]."""
    for pattern in _SECRET_PATTERNS:
        message = pattern.sub("[REDACTED]", message)
    return message


class SecureJsonFormatter(logging.Formatter):
    """JSON formatter that scrubs secrets from log records."""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        message = _scrub_secrets(message)

        log_entry: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": _scrub_secrets(record.getMessage()),
        }

        # Attach structured extra fields if present
        for field in (
            "request_id",
            "agent_node",
            "tool_name",
            "execution_time",
            "status",
            "error_type",
        ):
            val = getattr(record, field, None)
            if val is not None:
                log_entry[field] = val

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger with a secure JSON handler."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(SecureJsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger


def configure_logging(log_level: str = "INFO") -> None:
    """Configure root logging level."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.getLogger().setLevel(numeric_level)
    # Apply to agent package loggers
    get_logger("ai_agent").setLevel(numeric_level)


class AgentLogger:
    """Contextual logger that automatically attaches agent metadata."""

    def __init__(
        self,
        name: str,
        request_id: Optional[str] = None,
        agent_node: Optional[str] = None,
    ) -> None:
        self._logger = get_logger(name)
        self._request_id = request_id
        self._agent_node = agent_node

    def _extra(self, **kwargs: Any) -> dict[str, Any]:
        extra: dict[str, Any] = {}
        if self._request_id:
            extra["request_id"] = self._request_id
        if self._agent_node:
            extra["agent_node"] = self._agent_node
        extra.update(kwargs)
        return extra

    def info(self, msg: str, **kwargs: Any) -> None:
        self._logger.info(_scrub_secrets(msg), extra=self._extra(**kwargs))

    def warning(self, msg: str, **kwargs: Any) -> None:
        self._logger.warning(_scrub_secrets(msg), extra=self._extra(**kwargs))

    def error(self, msg: str, **kwargs: Any) -> None:
        self._logger.error(_scrub_secrets(msg), extra=self._extra(**kwargs))

    def debug(self, msg: str, **kwargs: Any) -> None:
        self._logger.debug(_scrub_secrets(msg), extra=self._extra(**kwargs))

    def tool_call(
        self,
        tool_name: str,
        status: str,
        execution_time: float,
        **kwargs: Any,
    ) -> None:
        self._logger.info(
            f"Tool call: {tool_name}",
            extra=self._extra(
                tool_name=tool_name,
                status=status,
                execution_time=execution_time,
                **kwargs,
            ),
        )
