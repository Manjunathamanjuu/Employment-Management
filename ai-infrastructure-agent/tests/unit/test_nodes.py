"""Unit tests for LangGraph node functions."""

from __future__ import annotations

import pytest

from app.agent.state import (
    AgentState,
    ApprovalStatus,
    ConfidenceLevel,
    EvidenceItem,
    InvestigationStatus,
    InvestigationPlan,
    InvestigationStep,
    ToolResult,
    RootCauseAnalysis,
    RiskLevel,
    RemediationPlan,
    RemediationAction,
)

pytestmark = pytest.mark.unit


def _make_state(**kwargs) -> AgentState:
    defaults = {
        "user_request": "Why is my pod failing?",
        "approval_status": ApprovalStatus.PENDING,
    }
    defaults.update(kwargs)
    return AgentState(**defaults)


# ---------------------------------------------------------------------------
# request_analyzer
# ---------------------------------------------------------------------------

class TestRequestAnalyzer:
    def test_valid_request_transitions_to_investigating(self):
        from app.agent.nodes import request_analyzer
        state = _make_state(user_request="Why is my pod failing?")
        result = request_analyzer(state)
        assert result["status"] == InvestigationStatus.INVESTIGATING

    def test_empty_request_transitions_to_failed(self):
        from app.agent.nodes import request_analyzer
        state = _make_state(user_request="")
        result = request_analyzer(state)
        assert result["status"] == InvestigationStatus.FAILED
        assert result["errors"]

    def test_whitespace_only_request_fails(self):
        from app.agent.nodes import request_analyzer
        state = _make_state(user_request="   ")
        result = request_analyzer(state)
        assert result["status"] == InvestigationStatus.FAILED

    def test_long_request_is_truncated(self):
        from app.agent.nodes import request_analyzer
        state = _make_state(user_request="x" * 3000)
        result = request_analyzer(state)
        assert result["status"] == InvestigationStatus.INVESTIGATING
        assert len(result["user_request"]) == 2000

    def test_step_counter_incremented(self):
        from app.agent.nodes import request_analyzer
        state = _make_state(user_request="test")
        result = request_analyzer(state)
        assert result["current_step"] == 1

    def test_preserves_existing_errors(self):
        from app.agent.nodes import request_analyzer
        state = _make_state(user_request="", errors=["pre-existing error"])
        result = request_analyzer(state)
        assert "pre-existing error" in result["errors"]


# ---------------------------------------------------------------------------
# investigation_planner
# ---------------------------------------------------------------------------

class TestInvestigationPlanner:
    def test_creates_plan(self):
        from app.agent.nodes import investigation_planner
        state = _make_state(
            user_request="Why is my pod failing?",
            status=InvestigationStatus.INVESTIGATING,
        )
        result = investigation_planner(state)
        assert result["investigation_plan"] is not None

    def test_plan_has_steps(self):
        from app.agent.nodes import investigation_planner
        state = _make_state(
            user_request="Why is my pod failing?",
            status=InvestigationStatus.INVESTIGATING,
        )
        result = investigation_planner(state)
        plan = result["investigation_plan"]
        assert len(plan.steps) > 0

    def test_plan_has_summary(self):
        from app.agent.nodes import investigation_planner
        state = _make_state(user_request="connection refused in my app")
        result = investigation_planner(state)
        assert result["investigation_plan"].summary

    def test_step_counter_incremented(self):
        from app.agent.nodes import investigation_planner
        state = _make_state(user_request="test", current_step=1)
        result = investigation_planner(state)
        assert result["current_step"] == 2


# ---------------------------------------------------------------------------
# tool_executor
# ---------------------------------------------------------------------------

class TestToolExecutor:
    def _state_with_plan(self) -> AgentState:
        """Plan using only namespace-only tools (no resource-name required)."""
        plan = InvestigationPlan(
            summary="Test plan",
            steps=[
                InvestigationStep(description="List pods", tool="get_pods",
                                  parameters={"namespace": "employment-management"}),
                InvestigationStep(description="Get events", tool="get_events",
                                  parameters={"namespace": "employment-management"}),
            ],
        )
        return _make_state(
            user_request="test",
            investigation_plan=plan,
            status=InvestigationStatus.INVESTIGATING,
        )

    def test_executes_all_pending_steps(self):
        from app.agent.nodes import tool_executor
        from unittest.mock import patch, MagicMock
        import subprocess as sp
        mock_proc = MagicMock(spec=sp.CompletedProcess)
        mock_proc.stdout = "NAME  READY  STATUS\npod/x  1/1  Running"
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        with patch("subprocess.run", return_value=mock_proc):
            state = self._state_with_plan()
            result = tool_executor(state)
        assert len(result["tool_results"]) == 2

    def test_all_steps_marked_completed(self):
        from app.agent.nodes import tool_executor
        from unittest.mock import patch, MagicMock
        import subprocess as sp
        mock_proc = MagicMock(spec=sp.CompletedProcess)
        mock_proc.stdout = ""
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        with patch("subprocess.run", return_value=mock_proc):
            state = self._state_with_plan()
            result = tool_executor(state)
        plan = result["investigation_plan"]
        assert all(s.status == "COMPLETED" for s in plan.steps)

    def test_no_plan_returns_gracefully(self):
        from app.agent.nodes import tool_executor
        state = _make_state(user_request="test")
        result = tool_executor(state)
        assert "current_step" in result

    def test_tool_results_have_required_fields(self):
        from app.agent.nodes import tool_executor
        from unittest.mock import patch, MagicMock
        import subprocess as sp
        mock_proc = MagicMock(spec=sp.CompletedProcess)
        mock_proc.stdout = "NAME  STATUS\npod  Running"
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        with patch("subprocess.run", return_value=mock_proc):
            state = self._state_with_plan()
            result = tool_executor(state)
        for tr in result["tool_results"]:
            assert tr.tool_name
            assert tr.status
            assert tr.command_type

    def test_get_pods_returns_kubectl_output(self):
        from app.agent.nodes import tool_executor
        from unittest.mock import patch, MagicMock
        import subprocess as sp
        crashloop_stdout = (
            "NAME  READY  STATUS  RESTARTS\n"
            "employment-management-abc  0/1  CrashLoopBackOff  5"
        )
        mock_proc = MagicMock(spec=sp.CompletedProcess)
        mock_proc.stdout = crashloop_stdout
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        plan = InvestigationPlan(
            summary="Test",
            steps=[InvestigationStep(
                description="Get pods",
                tool="get_pods",
                parameters={"namespace": "employment-management"},
            )],
        )
        state = _make_state(user_request="test", investigation_plan=plan)
        with patch("subprocess.run", return_value=mock_proc):
            result = tool_executor(state)
        assert "CrashLoopBackOff" in result["tool_results"][0].stdout

    def test_unknown_tool_uses_mock_fallback(self):
        from app.agent.nodes import tool_executor
        plan = InvestigationPlan(
            summary="Test",
            steps=[InvestigationStep(
                description="Unknown tool",
                tool="some_future_tool",
                parameters={"namespace": "employment-management"},
            )],
        )
        state = _make_state(user_request="test", investigation_plan=plan)
        result = tool_executor(state)
        assert len(result["tool_results"]) == 1

    def test_validation_error_recorded_not_raised(self):
        """Tool parameter validation errors are captured, not raised."""
        from app.agent.nodes import tool_executor
        plan = InvestigationPlan(
            summary="Test",
            steps=[InvestigationStep(
                description="Describe pod with injection",
                tool="describe_pod",
                parameters={"pod_name": "pod; rm -rf /",
                            "namespace": "employment-management"},
            )],
        )
        state = _make_state(user_request="test", investigation_plan=plan)
        result = tool_executor(state)
        tr = result["tool_results"][0]
        assert tr.status == "validation_error"


# ---------------------------------------------------------------------------
# evidence_analyzer
# ---------------------------------------------------------------------------

class TestEvidenceAnalyzer:
    def _state_with_results(self) -> AgentState:
        results = [
            ToolResult(
                tool_name="get_pods",
                status="success",
                command_type="read",
                stdout="NAME  READY  STATUS  RESTARTS\npod/my-pod  0/1  CrashLoopBackOff  5",
            ),
            ToolResult(
                tool_name="get_pod_logs",
                status="success",
                command_type="read",
                stdout="ERROR Failed to connect: Connection refused\nFATAL Exiting with code 1",
            ),
        ]
        return _make_state(user_request="test", tool_results=results)

    def test_extracts_crashloopbackoff_evidence(self):
        from app.agent.nodes import evidence_analyzer
        state = self._state_with_results()
        result = evidence_analyzer(state)
        observations = [e.observation for e in result["evidence"]]
        assert any("CrashLoopBackOff" in obs for obs in observations)

    def test_extracts_connection_refused_evidence(self):
        from app.agent.nodes import evidence_analyzer
        state = self._state_with_results()
        result = evidence_analyzer(state)
        observations = [e.observation for e in result["evidence"]]
        assert any("Connection refused" in obs for obs in observations)

    def test_inference_is_flagged(self):
        from app.agent.nodes import evidence_analyzer
        state = self._state_with_results()
        result = evidence_analyzer(state)
        assert any(e.is_inference for e in result["evidence"])

    def test_issues_populated(self):
        from app.agent.nodes import evidence_analyzer
        state = self._state_with_results()
        result = evidence_analyzer(state)
        assert len(result["issues"]) > 0

    def test_no_tool_results_produces_no_evidence(self):
        from app.agent.nodes import evidence_analyzer
        state = _make_state(user_request="test", tool_results=[])
        result = evidence_analyzer(state)
        assert result["evidence"] == []


# ---------------------------------------------------------------------------
# root_cause_analyzer
# ---------------------------------------------------------------------------

class TestRootCauseAnalyzer:
    def _state_with_evidence(self) -> AgentState:
        evidence = [
            EvidenceItem(
                source="get_pods", resource="pod/my-pod",
                observation="Pod is in CrashLoopBackOff state",
                confidence=ConfidenceLevel.HIGH,
            ),
            EvidenceItem(
                source="get_pod_logs", resource="pod/my-pod",
                observation="Application log: Connection refused on startup",
                confidence=ConfidenceLevel.HIGH,
            ),
            EvidenceItem(
                source="get_pod_logs", resource="pod/my-pod",
                observation="Container exiting with code 1 (application error)",
                confidence=ConfidenceLevel.HIGH,
            ),
        ]
        return _make_state(
            user_request="test",
            evidence=evidence,
            status=InvestigationStatus.INVESTIGATING,
        )

    def test_high_confidence_with_full_evidence(self):
        from app.agent.nodes import root_cause_analyzer
        state = self._state_with_evidence()
        result = root_cause_analyzer(state)
        assert result["confidence"] == ConfidenceLevel.HIGH

    def test_root_cause_populated(self):
        from app.agent.nodes import root_cause_analyzer
        state = self._state_with_evidence()
        result = root_cause_analyzer(state)
        assert result["root_cause"] is not None
        assert result["root_cause"].root_cause

    def test_insufficient_evidence_without_confirmed(self):
        from app.agent.nodes import root_cause_analyzer
        state = _make_state(user_request="test", evidence=[])
        result = root_cause_analyzer(state)
        assert result["confidence"] == ConfidenceLevel.INSUFFICIENT

    def test_insufficient_returns_no_hallucination(self):
        from app.agent.nodes import root_cause_analyzer
        state = _make_state(user_request="test", evidence=[])
        result = root_cause_analyzer(state)
        assert "Insufficient evidence" in result["root_cause"].root_cause

    def test_status_transitions_to_analyzed(self):
        from app.agent.nodes import root_cause_analyzer
        state = self._state_with_evidence()
        result = root_cause_analyzer(state)
        assert result["status"] == InvestigationStatus.ANALYZED

    def test_alternative_causes_present(self):
        from app.agent.nodes import root_cause_analyzer
        state = self._state_with_evidence()
        result = root_cause_analyzer(state)
        assert len(result["root_cause"].alternative_causes) > 0

    def test_medium_confidence_with_only_crashloop(self):
        from app.agent.nodes import root_cause_analyzer
        evidence = [EvidenceItem(
            source="get_pods", resource="pod/my-pod",
            observation="Pod is in CrashLoopBackOff state",
            confidence=ConfidenceLevel.HIGH,
        )]
        state = _make_state(user_request="test", evidence=evidence)
        result = root_cause_analyzer(state)
        assert result["confidence"] in (ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH)


# ---------------------------------------------------------------------------
# remediation_planner
# ---------------------------------------------------------------------------

class TestRemediationPlanner:
    def _state_with_rca(self) -> AgentState:
        from app.agent.nodes import root_cause_analyzer, evidence_analyzer
        evidence = [
            EvidenceItem(source="get_pods", resource="pod/my-pod",
                         observation="Pod is in CrashLoopBackOff state",
                         confidence=ConfidenceLevel.HIGH),
            EvidenceItem(source="get_pod_logs", resource="pod/my-pod",
                         observation="Application log: Connection refused on startup",
                         confidence=ConfidenceLevel.HIGH),
            EvidenceItem(source="get_pod_logs", resource="pod/my-pod",
                         observation="Container exiting with code 1 (application error)",
                         confidence=ConfidenceLevel.HIGH),
        ]
        rca = RootCauseAnalysis(
            incident_status="ACTIVE",
            affected_resource="pod/my-pod",
            root_cause="Connection refused",
            confidence=ConfidenceLevel.HIGH,
            reasoning_summary="test",
        )
        return _make_state(
            user_request="test",
            evidence=evidence,
            root_cause=rca,
            confidence=ConfidenceLevel.HIGH,
            status=InvestigationStatus.ANALYZED,
        )

    def test_creates_remediation_plan(self):
        from app.agent.nodes import remediation_planner
        state = self._state_with_rca()
        result = remediation_planner(state)
        assert result.get("remediation_plan") is not None

    def test_all_actions_require_approval(self):
        from app.agent.nodes import remediation_planner
        state = self._state_with_rca()
        result = remediation_planner(state)
        for action in result["remediation_plan"].actions:
            assert action.approval_required is True

    def test_approval_status_pending(self):
        from app.agent.nodes import remediation_planner
        state = self._state_with_rca()
        result = remediation_planner(state)
        assert result["approval_status"] == ApprovalStatus.PENDING

    def test_skips_with_insufficient_confidence(self):
        from app.agent.nodes import remediation_planner
        state = _make_state(
            user_request="test",
            confidence=ConfidenceLevel.INSUFFICIENT,
            status=InvestigationStatus.ANALYZED,
        )
        result = remediation_planner(state)
        assert result["status"] == InvestigationStatus.REMEDIATION_PLANNED

    def test_all_actions_have_rollback(self):
        from app.agent.nodes import remediation_planner
        state = self._state_with_rca()
        result = remediation_planner(state)
        for action in result["remediation_plan"].actions:
            assert action.rollback


# ---------------------------------------------------------------------------
# approval_gate
# ---------------------------------------------------------------------------

class TestApprovalGate:
    def test_pending_pauses_workflow(self):
        from app.agent.nodes import approval_gate
        state = _make_state(user_request="test", approval_status=ApprovalStatus.PENDING)
        result = approval_gate(state)
        assert result["status"] == InvestigationStatus.AWAITING_APPROVAL

    def test_approved_allows_execution(self):
        from app.agent.nodes import approval_gate
        state = _make_state(user_request="test", approval_status=ApprovalStatus.APPROVED)
        result = approval_gate(state)
        assert result["status"] == InvestigationStatus.REMEDIATION_APPROVED

    def test_rejected_blocks_execution(self):
        from app.agent.nodes import approval_gate
        state = _make_state(user_request="test", approval_status=ApprovalStatus.REJECTED)
        result = approval_gate(state)
        assert result["status"] == InvestigationStatus.REMEDIATION_REJECTED


# ---------------------------------------------------------------------------
# remediation_executor
# ---------------------------------------------------------------------------

class TestRemediationExecutor:
    def test_blocks_without_approval(self):
        from app.agent.nodes import remediation_executor
        state = _make_state(user_request="test", approval_status=ApprovalStatus.PENDING)
        result = remediation_executor(state)
        assert result["status"] == InvestigationStatus.FAILED
        assert any("SAFETY" in e for e in result["errors"])

    def test_approved_proceeds_as_stub(self):
        from app.agent.nodes import remediation_executor
        state = _make_state(user_request="test", approval_status=ApprovalStatus.APPROVED)
        result = remediation_executor(state)
        assert result["status"] == InvestigationStatus.REMEDIATING

    def test_rejected_blocks_execution(self):
        from app.agent.nodes import remediation_executor
        state = _make_state(user_request="test", approval_status=ApprovalStatus.REJECTED)
        result = remediation_executor(state)
        assert result["status"] == InvestigationStatus.FAILED


# ---------------------------------------------------------------------------
# final_report
# ---------------------------------------------------------------------------

class TestFinalReport:
    def test_generates_report(self):
        from app.agent.nodes import final_report
        state = _make_state(
            user_request="Why is my pod failing?",
            issues=["CrashLoopBackOff"],
            confidence=ConfidenceLevel.HIGH,
        )
        result = final_report(state)
        assert result["final_report"] is not None

    def test_report_contains_request_id(self):
        from app.agent.nodes import final_report
        state = _make_state(user_request="test")
        result = final_report(state)
        assert result["final_report"].request_id == state.request_id

    def test_report_status_completed(self):
        from app.agent.nodes import final_report
        state = _make_state(user_request="test")
        result = final_report(state)
        assert result["status"] == InvestigationStatus.COMPLETED

    def test_report_includes_issues(self):
        from app.agent.nodes import final_report
        state = _make_state(user_request="test", issues=["issue1", "issue2"])
        result = final_report(state)
        assert "issue1" in result["final_report"].issues_found
