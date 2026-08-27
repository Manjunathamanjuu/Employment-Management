"""Phase 7 — CloudOps frontend is served by the existing FastAPI app.

These tests do not rebuild the UI. They verify the existing SPA:
- is served at /
- does not shadow API routes
- calls only existing backend endpoints
- includes the required CloudOps pages
- never embeds secrets
"""

from __future__ import annotations

import os
import re

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

FRONTEND = os.path.join(
    os.path.dirname(__file__), "..", "..", "frontend", "index.html"
)

REQUIRED_PAGES = [
    "Dashboard",
    "AI Troubleshooter",
    "Investigations",
    "Incidents",
    "Infrastructure",
    "Kubernetes",
    "Docker",
    "Terraform",
    "Remediation",
    "Audit Logs",
    "Settings",
]

ALLOWED_API_PATHS = {
    "/health",
    "/ready",
    "/api/v1/troubleshoot",
    "/api/v1/approve",
}


@pytest.fixture
def ui_client():
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


def _frontend_source() -> str:
    with open(FRONTEND, encoding="utf-8") as fh:
        return fh.read()


class TestFrontendServed:
    def test_index_html_exists(self):
        assert os.path.isfile(FRONTEND)

    def test_root_returns_html(self, ui_client):
        response = ui_client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "CloudOps" in response.text

    def test_health_not_shadowed_by_static_mount(self, ui_client):
        response = ui_client.get("/health")
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("application/json")
        assert response.json()["status"] == "ok"

    def test_ready_still_json(self, ui_client):
        response = ui_client.get("/ready")
        assert response.status_code in (200, 503)
        assert "ready" in response.json()


class TestRequiredPages:
    @pytest.mark.parametrize("label", REQUIRED_PAGES)
    def test_page_label_present(self, label):
        source = _frontend_source()
        assert label in source, f"CloudOps UI missing page/section: {label}"

    def test_remediation_is_a_nav_item(self):
        source = _frontend_source()
        assert "id:'remediation'" in source or 'id:"remediation"' in source
        assert "label:'Remediation'" in source or 'label:"Remediation"' in source

    def test_approval_copy_present(self):
        source = _frontend_source()
        assert "Human Approval Required" in source
        assert "/api/v1/approve" in source


class TestApiClientSurface:
    def test_only_existing_backend_endpoints(self):
        source = _frontend_source()
        fetch_urls = re.findall(r"fetch\(`\$\{BASE\}([^`]+)`", source)
        extra = [path.split("?")[0] for path in fetch_urls if path.split("?")[0] not in ALLOWED_API_PATHS]
        assert extra == [], f"Frontend calls unknown APIs: {extra}"

    def test_does_not_define_new_agent_api(self):
        source = _frontend_source()
        assert "/api/v2/" not in source
        assert "/api/v1/chat" not in source


class TestFrontendSecurity:
    def test_no_hardcoded_openai_key(self):
        source = _frontend_source()
        assert not re.search(r"sk-[A-Za-z0-9]{20,}", source)

    def test_no_password_or_token_literals(self):
        source = _frontend_source().lower()
        assert "openai_api_key=" not in source
        assert "bearer eyj" not in source

    def test_security_headers_on_ui(self, ui_client):
        response = ui_client.get("/")
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"
