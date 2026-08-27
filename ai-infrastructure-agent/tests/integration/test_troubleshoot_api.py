"""Integration tests for the /api/v1/troubleshoot endpoint with LangGraph wired in."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder-key-for-testing-only")
    import app.config as cfg_module
    import app.api.routes as routes_module
    import app.main as main_module
    new_settings = cfg_module.Settings()
    cfg_module.settings = new_settings
    routes_module.settings = new_settings
    main_module.settings = new_settings
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


class TestTroubleshootWorkflow:
    def test_returns_202(self, client):
        response = client.post(
            "/api/v1/troubleshoot",
            json={"request": "Why is my pod failing?"},
        )
        assert response.status_code == 202

    def test_response_has_request_id(self, client):
        response = client.post(
            "/api/v1/troubleshoot",
            json={"request": "Why is my pod failing?"},
        )
        data = response.json()
        assert "request_id" in data
        assert data["request_id"]

    def test_response_has_status(self, client):
        response = client.post(
            "/api/v1/troubleshoot",
            json={"request": "Why is my pod failing?"},
        )
        data = response.json()
        assert "status" in data

    def test_response_has_evidence(self, client):
        response = client.post(
            "/api/v1/troubleshoot",
            json={"request": "Why is my pod failing?"},
        )
        data = response.json()
        assert "evidence" in data
        assert isinstance(data["evidence"], list)
        assert len(data["evidence"]) > 0

    def test_response_has_root_cause(self, client):
        response = client.post(
            "/api/v1/troubleshoot",
            json={"request": "Why is my pod failing?"},
        )
        data = response.json()
        assert "root_cause" in data
        assert data["root_cause"] is not None
        assert data["root_cause"]["root_cause"]

    def test_response_has_remediation(self, client):
        response = client.post(
            "/api/v1/troubleshoot",
            json={"request": "Why is my pod failing?"},
        )
        data = response.json()
        assert "remediation" in data
        assert isinstance(data["remediation"], list)
        assert len(data["remediation"]) > 0

    def test_approval_required_true(self, client):
        response = client.post(
            "/api/v1/troubleshoot",
            json={"request": "Why is my pod failing?"},
        )
        data = response.json()
        assert data["approval_required"] is True

    def test_approval_status_pending(self, client):
        response = client.post(
            "/api/v1/troubleshoot",
            json={"request": "Why is my pod failing?"},
        )
        data = response.json()
        assert data["approval_status"] == "PENDING"

    def test_confidence_populated(self, client):
        response = client.post(
            "/api/v1/troubleshoot",
            json={"request": "Why is my pod failing?"},
        )
        data = response.json()
        assert data["confidence"] in ("HIGH", "MEDIUM", "LOW", "INSUFFICIENT")

    def test_remediation_actions_have_required_fields(self, client):
        response = client.post(
            "/api/v1/troubleshoot",
            json={"request": "Why is my pod failing?"},
        )
        data = response.json()
        for action in data["remediation"]:
            assert "action" in action
            assert "risk" in action
            assert "approval_required" in action
            assert action["approval_required"] is True

    def test_response_no_stack_trace(self, client):
        response = client.post(
            "/api/v1/troubleshoot",
            json={"request": "Why is my pod failing?"},
        )
        assert "Traceback" not in response.text
        assert "File " not in response.text

    def test_no_secrets_in_response(self, client):
        response = client.post(
            "/api/v1/troubleshoot",
            json={"request": "Why is my pod failing?"},
        )
        assert "sk-test" not in response.text
        assert "OPENAI_API_KEY" not in response.text
