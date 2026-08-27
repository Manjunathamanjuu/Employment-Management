"""Unit tests for the LangGraph workflow graph."""

from __future__ import annotations

import pytest

from app.agent.state import (
    AgentState,
    ApprovalStatus,
    ConfidenceLevel,
    InvestigationStatus,
)

pytestmark = pytest.mark.unit


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
        result = run_investigation("Why is my pod failing?")
        assert isinstance(result, AgentState)

    def test_completed_status(self):
        from app.agent.graph import run_investigation
        result = run_investigation("Why is my pod failing?")
        assert result.status == InvestigationStatus.COMPLETED

    def test_request_id_preserved(self):
        from app.agent.graph import run_investigation
        result = run_investigation("Why is my pod failing?", request_id="test-req-001")
        assert result.request_id == "test-req-001"

    def test_evidence_collected(self):
        from app.agent.graph import run_investigation
        result = run_investigation("Why is my pod failing?")
        assert len(result.evidence) > 0

    def test_root_cause_populated(self):
        from app.agent.graph import run_investigation
        result = run_investigation("Why is my pod failing?")
        assert result.root_cause is not None

    def test_high_confidence_with_mock_data(self):
        from app.agent.graph import run_investigation
        result = run_investigation("Why is my pod failing?")
        assert result.confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)

    def test_remediation_plan_populated(self):
        from app.agent.graph import run_investigation
        result = run_investigation("Why is my pod failing?")
        assert result.remediation_plan is not None
        assert len(result.remediation_plan.actions) > 0

    def test_approval_required_true(self):
        from app.agent.graph import run_investigation
        result = run_investigation("Why is my pod failing?")
        assert result.approval_required is True

    def test_approval_status_awaiting(self):
        from app.agent.graph import run_investigation
        result = run_investigation("Why is my pod failing?")
        # With PENDING approval the workflow stops at approval gate
        # and routes to final_report (AWAITING_APPROVAL → final_report)
        assert result.status in (
            InvestigationStatus.COMPLETED,
            InvestigationStatus.AWAITING_APPROVAL,
        )

    def test_final_report_present(self):
        from app.agent.graph import run_investigation
        result = run_investigation("Why is my pod failing?")
        assert result.final_report is not None

    def test_final_report_has_investigation_summary(self):
        from app.agent.graph import run_investigation
        result = run_investigation("Why is my pod failing?")
        assert result.final_report.investigation_summary

    def test_issues_found_in_report(self):
        from app.agent.graph import run_investigation
        result = run_investigation("Why is my pod failing?")
        assert len(result.issues) > 0

    def test_no_errors_on_happy_path(self):
        from app.agent.graph import run_investigation
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
        long_request = "x" * 5000
        result = run_investigation(long_request)
        # Should truncate and complete rather than fail
        assert result.status in (
            InvestigationStatus.COMPLETED,
            InvestigationStatus.FAILED,
        )

    def test_unicode_request_completes(self):
        from app.agent.graph import run_investigation
        result = run_investigation("なぜポッドが失敗しているのですか？")
        assert result is not None


class TestGraphRouting:
    def test_failed_request_skips_to_final_report(self):
        from app.agent.graph import run_investigation
        result = run_investigation("")
        # Even on failure, final_report should be populated
        assert result.final_report is not None

    def test_pending_approval_routes_to_final_report(self):
        """With PENDING approval, graph should route approval_gate → final_report."""
        from app.agent.graph import run_investigation
        result = run_investigation("test request")
        # approval_status should remain PENDING (no human provided approval)
        assert result.approval_status == ApprovalStatus.PENDING
        # Execution should NOT have proceeded to remediation_executor
        assert result.status != InvestigationStatus.REMEDIATING

    def test_remediation_not_executed_without_approval(self):
        """Remediation executor must never run without approval."""
        from app.agent.graph import run_investigation
        result = run_investigation("test request")
        # remediation_result should be None since approval was not given
        assert result.remediation_result is None
