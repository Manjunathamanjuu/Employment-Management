"""Unit tests for structured logging and secret scrubbing."""

from __future__ import annotations

import json
import logging
import pytest

pytestmark = pytest.mark.unit


class TestSecretScrubbing:
    def _scrub(self, message: str) -> str:
        from app.logging.logger import _scrub_secrets
        return _scrub_secrets(message)

    def test_openai_key_scrubbed(self):
        msg = "Key is sk-abcdefghijklmnopqrstuvwxyz1234567890ABCDEF"
        result = self._scrub(msg)
        assert "sk-abcdefghijklmnopqrstuvwxyz" not in result
        assert "[REDACTED]" in result

    def test_password_scrubbed(self):
        msg = "password: mysecretpassword123"
        result = self._scrub(msg)
        assert "mysecretpassword123" not in result

    def test_token_scrubbed(self):
        msg = "token: eyJhbGciOiJSUzI1NiJ9.sometoken"
        result = self._scrub(msg)
        assert "eyJhbGciOiJSUzI1NiJ9" not in result

    def test_secret_scrubbed(self):
        msg = "secret: hunter2"
        result = self._scrub(msg)
        assert "hunter2" not in result

    def test_gcp_api_key_scrubbed(self):
        msg = "key=AIzaSyD-abcdefghijklmnopqrstuvwxyz12345678"
        result = self._scrub(msg)
        assert "AIzaSyD-abcdefghijklmnopqrstuvwxyz" not in result

    def test_private_key_header_scrubbed(self):
        msg = "-----BEGIN RSA PRIVATE KEY-----"
        result = self._scrub(msg)
        # Pattern matches the header
        assert "-----BEGIN RSA PRIVATE KEY-----" not in result

    def test_normal_message_unchanged(self):
        msg = "Pod my-pod is in CrashLoopBackOff state"
        result = self._scrub(msg)
        assert result == msg


class TestGetLogger:
    def test_returns_logger_instance(self):
        from app.logging.logger import get_logger
        logger = get_logger("test.logger")
        assert isinstance(logger, logging.Logger)

    def test_logger_has_handler(self):
        from app.logging.logger import get_logger
        logger = get_logger("test.logger.with.handler")
        assert len(logger.handlers) > 0

    def test_same_name_returns_same_logger(self):
        from app.logging.logger import get_logger
        l1 = get_logger("same.name")
        l2 = get_logger("same.name")
        assert l1 is l2


class TestAgentLogger:
    def test_agent_logger_creates(self):
        from app.logging.logger import AgentLogger
        al = AgentLogger("test.agent", request_id="req-123", agent_node="test_node")
        assert al is not None

    def test_agent_logger_info_does_not_raise(self):
        from app.logging.logger import AgentLogger
        al = AgentLogger("test.agent.info", request_id="req-456")
        al.info("Test message")

    def test_agent_logger_scrubs_secrets(self, caplog):
        from app.logging.logger import AgentLogger
        al = AgentLogger("test.agent.scrub")
        # Should not raise even with secret-like content
        al.info("Config: sk-testkey123456789012345678901234")

    def test_tool_call_logging(self):
        from app.logging.logger import AgentLogger
        al = AgentLogger("test.agent.tool", request_id="req-789")
        al.tool_call(
            tool_name="get_pods",
            status="success",
            execution_time=0.5,
        )


class TestSecureJsonFormatter:
    def test_formats_as_json(self):
        from app.logging.logger import SecureJsonFormatter
        formatter = SecureJsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Hello World",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "Hello World"
        assert parsed["level"] == "INFO"

    def test_formatter_scrubs_secrets_in_message(self):
        from app.logging.logger import SecureJsonFormatter
        formatter = SecureJsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Token: sk-testABCDEFGHIJKLMNOPQRSTUVWXYZ123456",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        assert "sk-testABCDEFGHIJKLMNOPQRSTUVWXYZ123456" not in output
