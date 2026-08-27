"""Security tests — verify secrets never appear in logs, responses, or config dumps."""

from __future__ import annotations

import json
import logging
import pytest

pytestmark = pytest.mark.security


class TestSecretNeverInConfig:
    def test_openai_key_redacted_in_dict(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-realsecretkey1234567890ABCDEFGH")
        from app.config import Settings
        s = Settings()
        d = s.redacted_dict()
        assert "sk-realsecretkey" not in json.dumps(d)
        assert d.get("openai_api_key") == "[REDACTED]"

    def test_env_file_not_committed(self):
        import os
        # .env must not exist in the project (only .env.example is allowed)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        assert not os.path.exists(os.path.join(project_root, ".env")), (
            ".env file must not be committed to the repository"
        )

    def test_env_example_has_no_real_key(self):
        import os
        import re
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        example_path = os.path.join(project_root, ".env.example")
        if os.path.exists(example_path):
            with open(example_path) as f:
                content = f.read()
            # Must not contain a real OpenAI key pattern
            assert not re.search(r"sk-[A-Za-z0-9]{20,}", content), (
                ".env.example must not contain a real OpenAI API key"
            )


class TestSecretNeverInLogs:
    def test_logger_scrubs_openai_key(self):
        from app.logging.logger import _scrub_secrets
        key = "sk-testXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        scrubbed = _scrub_secrets(f"Using key: {key}")
        assert key not in scrubbed
        assert "[REDACTED]" in scrubbed

    def test_logger_scrubs_password(self):
        from app.logging.logger import _scrub_secrets
        msg = "DB connection: password=super_secret_pass_123"
        scrubbed = _scrub_secrets(msg)
        assert "super_secret_pass_123" not in scrubbed

    def test_logger_scrubs_token(self):
        from app.logging.logger import _scrub_secrets
        msg = "Bearer token: eyJhbGciOiJIUzI1NiJ9.payload.signature"
        scrubbed = _scrub_secrets(msg)
        assert "eyJhbGciOiJIUzI1NiJ9" not in scrubbed

    def test_json_formatter_scrubs_record(self):
        from app.logging.logger import SecureJsonFormatter
        formatter = SecureJsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="API key sk-secretkey123456789012345678901234567890",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        assert "sk-secretkey123456789012345678901234567890" not in output
        assert "[REDACTED]" in output


class TestSecretNeverInAPIResponse:
    @pytest.fixture
    def client(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder-key-for-testing-only")
        import app.config as cfg_module
        cfg_module.settings = cfg_module.Settings()
        from app.main import app
        from fastapi.testclient import TestClient
        return TestClient(app, raise_server_exceptions=False)

    def test_health_response_has_no_secret(self, client):
        response = client.get("/health")
        body = response.text
        assert "sk-test" not in body
        assert "OPENAI_API_KEY" not in body

    def test_ready_response_has_no_secret(self, client):
        response = client.get("/ready")
        body = response.text
        assert "sk-test" not in body
        assert "OPENAI_API_KEY" not in body

    def test_troubleshoot_response_has_no_secret(self, client):
        response = client.post(
            "/api/v1/troubleshoot",
            json={"request": "Why is my pod failing?"},
        )
        body = response.text
        assert "sk-test" not in body
        assert "OPENAI_API_KEY" not in body

    def test_error_response_no_internal_detail(self, monkeypatch):
        """Ensure 500 errors do not leak implementation details."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder-key-for-testing-only")
        import app.config as cfg_module
        cfg_module.settings = cfg_module.Settings()
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=False)
        # Sending malformed JSON
        response = client.post(
            "/api/v1/troubleshoot",
            data="not-json",
            headers={"Content-Type": "application/json"},
        )
        body = response.text
        assert "Traceback" not in body
        assert "File " not in body
