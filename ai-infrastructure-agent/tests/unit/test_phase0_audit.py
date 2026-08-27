"""Phase 0 — architecture audit artifact must exist and stay accurate enough to use."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.unit

_AUDIT = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "docs",
    "PHASE0_ARCHITECTURE_AUDIT.md",
)

_REQUIRED_HEADINGS = [
    "Repository layout",
    "Architecture (as implemented)",
    "Backend (FastAPI)",
    "AI agent (LangGraph)",
    "Infrastructure tools",
    "Evidence",
    "Root cause",
    "Remediation",
    "Frontend",
    "Security",
    "Observability",
    "Docker (CloudOps image)",
    "Docker Compose (CloudOps)",
    "Product phase status (0–16)",
]


class TestPhase0AuditDocument:
    def test_audit_file_exists(self):
        assert os.path.isfile(_AUDIT), (
            "Phase 0 audit missing: docs/PHASE0_ARCHITECTURE_AUDIT.md"
        )

    def test_audit_not_empty(self):
        with open(_AUDIT, encoding="utf-8") as fh:
            content = fh.read()
        assert len(content) > 500

    @pytest.mark.parametrize("heading", _REQUIRED_HEADINGS)
    def test_audit_has_required_section(self, heading):
        with open(_AUDIT, encoding="utf-8") as fh:
            content = fh.read()
        assert heading in content, f"Audit missing section: {heading}"

    def test_audit_does_not_claim_cloudops_compose_exists(self):
        with open(_AUDIT, encoding="utf-8") as fh:
            content = fh.read()
        assert "no** CloudOps compose" in content.lower() or (
            "There is **no** CloudOps compose" in content
        )

    def test_audit_records_no_llm_planner(self):
        with open(_AUDIT, encoding="utf-8") as fh:
            content = fh.read()
        assert "deterministic mock plan" in content
        assert "ChatOpenAI" in content
