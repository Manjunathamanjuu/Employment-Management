"""Integration tests for health and readiness endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.fixture
def app_client_no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import app.config as cfg_module
    cfg_module.settings = cfg_module.Settings()
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def app_client_with_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder-key-for-testing-only")
    import app.config as cfg_module
    new_settings = cfg_module.Settings()
    cfg_module.settings = new_settings
    # Patch every module that holds a reference to the settings singleton
    import app.api.routes as routes_module
    routes_module.settings = new_settings
    import app.main as main_module
    main_module.settings = new_settings
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoint:
    def test_health_returns_200(self, app_client_no_key):
        response = app_client_no_key.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok_status(self, app_client_no_key):
        response = app_client_no_key.get("/health")
        data = response.json()
        assert data["status"] == "ok"

    def test_health_returns_version(self, app_client_no_key):
        response = app_client_no_key.get("/health")
        data = response.json()
        assert "version" in data
        assert data["version"]

    def test_health_returns_timestamp(self, app_client_no_key):
        response = app_client_no_key.get("/health")
        data = response.json()
        assert "timestamp" in data

    def test_health_content_type_json(self, app_client_no_key):
        response = app_client_no_key.get("/health")
        assert "application/json" in response.headers["content-type"]


class TestReadinessEndpoint:
    def test_ready_returns_503_without_key(self, app_client_no_key):
        response = app_client_no_key.get("/ready")
        assert response.status_code == 503

    def test_ready_returns_false_without_key(self, app_client_no_key):
        response = app_client_no_key.get("/ready")
        data = response.json()
        assert data["ready"] is False

    def test_ready_returns_200_with_key(self, app_client_with_key):
        response = app_client_with_key.get("/ready")
        assert response.status_code == 200

    def test_ready_returns_true_with_key(self, app_client_with_key):
        response = app_client_with_key.get("/ready")
        data = response.json()
        assert data["ready"] is True

    def test_ready_includes_checks(self, app_client_with_key):
        response = app_client_with_key.get("/ready")
        data = response.json()
        assert "checks" in data
        assert "openai_key_configured" in data["checks"]


class TestTroubleshootEndpoint:
    def test_troubleshoot_returns_202(self, app_client_with_key):
        response = app_client_with_key.post(
            "/api/v1/troubleshoot",
            json={"request": "Why is my pod failing?"},
        )
        assert response.status_code == 202

    def test_troubleshoot_returns_request_id(self, app_client_with_key):
        response = app_client_with_key.post(
            "/api/v1/troubleshoot",
            json={"request": "Why is my pod failing?"},
        )
        data = response.json()
        assert "request_id" in data
        assert data["request_id"]

    def test_troubleshoot_empty_request_returns_422(self, app_client_with_key):
        response = app_client_with_key.post(
            "/api/v1/troubleshoot",
            json={"request": ""},
        )
        assert response.status_code == 422

    def test_troubleshoot_missing_request_field_returns_422(self, app_client_with_key):
        response = app_client_with_key.post(
            "/api/v1/troubleshoot",
            json={},
        )
        assert response.status_code == 422

    def test_troubleshoot_invalid_namespace_returns_422(self, app_client_with_key):
        response = app_client_with_key.post(
            "/api/v1/troubleshoot",
            json={"request": "test", "namespace": "ns; rm -rf /"},
        )
        assert response.status_code == 422

    def test_troubleshoot_with_valid_namespace(self, app_client_with_key):
        response = app_client_with_key.post(
            "/api/v1/troubleshoot",
            json={"request": "test", "namespace": "employment-management"},
        )
        assert response.status_code == 202

    def test_validation_error_no_stack_trace(self, app_client_with_key):
        response = app_client_with_key.post(
            "/api/v1/troubleshoot",
            json={"request": ""},
        )
        body = response.text
        assert "Traceback" not in body
        assert "traceback" not in body

    def test_troubleshoot_no_key_still_returns_response(self, app_client_no_key):
        """Endpoint should not expose internal errors about missing keys."""
        response = app_client_no_key.post(
            "/api/v1/troubleshoot",
            json={"request": "Why is my pod failing?"},
        )
        # Should return 202 (key requirement is a readiness concern, not per-request)
        assert response.status_code in (202, 503)
