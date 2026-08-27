"""Unit tests for the LangGraph workflow graph."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import subprocess as sp

import pytest

from app.agent.state import (
    AgentState,
    ApprovalStatus,
    ConfidenceLevel,
    InvestigationStatus,
)

pytestmark = pytest.mark.unit


def _mock_kubectl(stdout: str = "NAME  STATUS\npod  Running", returncode: int = 0):
    """Return a mock subprocess.CompletedProcess for kubectl calls."""
    m = MagicMock(spec=sp.CompletedProcess)
    m.stdout = stdout
    m.stderr = ""
    m.returncode = returncode
    return m


# Default mock kubectl output with CrashLoopBackOff for graph-level tests
_CRASH_STDOUT = (
    "NAME                                    READY   STATUS             RESTARTS\n"
    "employment-management-6d8f9b7c4-xkp2n   0/1     CrashLoopBackOff   5"
)


class TestLangChainCompat:
    def test_debug_attr_present_after_graph_import(self):
        from app.agent.compat import ensure_langchain_debug_attr

        ensure_langchain_debug_attr()
        import langchain

        assert hasattr(langchain, "debug")


class TestGraphBuild:
    def test_graph_builds_without_error(self):
        from app.agent.graph import build_graph
        graph = build_graph()
        assert graph is not None

    def test_get_graph_returns_singleton(self):
        from app.agent.graph import get_graph
        g1 = get_graph()
        g2 = get_graph()
        assert g1 is g2


class TestRunInvestigation:
    def test_returns_agent_state(self):
        from app.agent.graph import run_investigation
        with patch("subprocess.run", return_value=_mock_kubectl(_CRASH_STDOUT)):
            result = run_investigation("Why is my pod failing?")
        assert isinstance(result, AgentState)

    def test_completed_status(self):
        from app.agent.graph import run_investigation
        with patch("subprocess.run", return_value=_mock_kubectl(_CRASH_STDOUT)):
            result = run_investigation("Why is my pod failing?")
        assert result.status == InvestigationStatus.COMPLETED

    def test_request_id_preserved(self):
        from app.agent.graph import run_investigation
        with patch("subprocess.run", return_value=_mock_kubectl(_CRASH_STDOUT)):
            result = run_investigation("Why is my pod failing?", request_id="test-req-001")
        assert result.request_id == "test-req-001"

    def test_evidence_collected(self):
        from app.agent.graph import run_investigation
        with patch("subprocess.run", return_value=_mock_kubectl(_CRASH_STDOUT)):
            result = run_investigation("Why is my pod failing?")
        assert len(result.evidence) > 0

    def test_root_cause_populated(self):
        from app.agent.graph import run_investigation
        with patch("subprocess.run", return_value=_mock_kubectl(_CRASH_STDOUT)):
            result = run_investigation("Why is my pod failing?")
        assert result.root_cause is not None

    def test_confidence_with_crashloop_data(self):
        from app.agent.graph import run_investigation
        with patch("subprocess.run", return_value=_mock_kubectl(_CRASH_STDOUT)):
            result = run_investigation("Why is my pod failing?")
        assert result.confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW)

    def test_remediation_plan_populated(self):
        from app.agent.graph import run_investigation
        with patch("subprocess.run", return_value=_mock_kubectl(_CRASH_STDOUT)):
            result = run_investigation("Why is my pod failing?")
        assert result.remediation_plan is not None
        assert len(result.remediation_plan.actions) > 0

    def test_approval_required_true(self):
        from app.agent.graph import run_investigation
        with patch("subprocess.run", return_value=_mock_kubectl(_CRASH_STDOUT)):
            result = run_investigation("Why is my pod failing?")
        assert result.approval_required is True

    def test_approval_status_pending(self):
        from app.agent.graph import run_investigation
        with patch("subprocess.run", return_value=_mock_kubectl(_CRASH_STDOUT)):
            result = run_investigation("Why is my pod failing?")
        assert result.approval_status == ApprovalStatus.PENDING

    def test_final_report_present(self):
        from app.agent.graph import run_investigation
        with patch("subprocess.run", return_value=_mock_kubectl(_CRASH_STDOUT)):
            result = run_investigation("Why is my pod failing?")
        assert result.final_report is not None

    def test_final_report_has_investigation_summary(self):
        from app.agent.graph import run_investigation
        with patch("subprocess.run", return_value=_mock_kubectl(_CRASH_STDOUT)):
            result = run_investigation("Why is my pod failing?")
        assert result.final_report.investigation_summary

    def test_issues_found_in_report(self):
        from app.agent.graph import run_investigation
        with patch("subprocess.run", return_value=_mock_kubectl(_CRASH_STDOUT)):
            result = run_investigation("Why is my pod failing?")
        assert len(result.issues) > 0

    def test_no_errors_on_happy_path(self):
        from app.agent.graph import run_investigation
        with patch("subprocess.run", return_value=_mock_kubectl(_CRASH_STDOUT)):
            result = run_investigation("Why is my pod failing?")
        assert result.errors == []


class TestInvalidRequests:
    def test_empty_request_does_not_raise(self):
        from app.agent.graph import run_investigation
        result = run_investigation("")
        assert result.status == InvestigationStatus.FAILED

    def test_empty_request_has_error(self):
        from app.agent.graph import run_investigation
        result = run_investigation("")
        assert len(result.errors) > 0

    def test_whitespace_request_fails(self):
        from app.agent.graph import run_investigation
        result = run_investigation("   ")
        assert result.status == InvestigationStatus.FAILED

    def test_very_long_request_completes(self):
        from app.agent.graph import run_investigation
        with patch("subprocess.run", return_value=_mock_kubectl()):
            result = run_investigation("x" * 5000)
        assert result.status in (
            InvestigationStatus.COMPLETED,
            InvestigationStatus.FAILED,
        )

    def test_unicode_request_completes(self):
        from app.agent.graph import run_investigation
        with patch("subprocess.run", return_value=_mock_kubectl()):
            result = run_investigation("なぜポッドが失敗しているのですか？")
        assert result is not None


class TestGraphRouting:
    def test_failed_request_skips_to_final_report(self):
        from app.agent.graph import run_investigation
        result = run_investigation("")
        assert result.final_report is not None

    def test_pending_approval_routes_to_final_report(self):
        from app.agent.graph import run_investigation
        with patch("subprocess.run", return_value=_mock_kubectl(_CRASH_STDOUT)):
            result = run_investigation("test request")
        assert result.approval_status == ApprovalStatus.PENDING
        assert result.status != InvestigationStatus.REMEDIATING

    def test_remediation_not_executed_without_approval(self):
        from app.agent.graph import run_investigation
        with patch("subprocess.run", return_value=_mock_kubectl(_CRASH_STDOUT)):
            result = run_investigation("test request")
        assert result.remediation_result is None
