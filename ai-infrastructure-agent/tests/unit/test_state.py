"""Unit tests for Pydantic agent state models."""

from __future__ import annotations

import uuid
import pytest
from datetime import datetime, timezone

pytestmark = pytest.mark.unit


class TestAgentState:
    def test_minimal_creation(self):
        from app.agent.state import AgentState
        state = AgentState(user_request="Why is my pod failing?")
        assert state.user_request == "Why is my pod failing?"
        assert state.request_id  # auto-generated UUID
        assert state.errors == []
        assert state.tool_results == []
        assert state.evidence == []

    def test_request_id_is_uuid(self):
        from app.agent.state import AgentState
        state = AgentState(user_request="test")
        uuid.UUID(state.request_id)  # raises if invalid

    def test_default_status_is_pending(self):
        from app.agent.state import AgentState, InvestigationStatus
        state = AgentState(user_request="test")
        assert state.status == InvestigationStatus.PENDING

    def test_default_approval_required(self):
        from app.agent.state import AgentState
        state = AgentState(user_request="test")
        assert state.approval_required is True

    def test_default_confidence_insufficient(self):
        from app.agent.state import AgentState, ConfidenceLevel
        state = AgentState(user_request="test")
        assert state.confidence == ConfidenceLevel.INSUFFICIENT


class TestEvidenceItem:
    def test_minimal_creation(self):
        from app.agent.state import EvidenceItem, ConfidenceLevel
        ev = EvidenceItem(
            source="kubectl",
            resource="pod/my-pod",
            observation="Pod is in CrashLoopBackOff",
        )
        assert ev.is_inference is False
        assert ev.confidence == ConfidenceLevel.MEDIUM

    def test_inference_flag(self):
        from app.agent.state import EvidenceItem
        ev = EvidenceItem(
            source="llm",
            resource="pod/my-pod",
            observation="Application cannot connect to database",
            is_inference=True,
        )
        assert ev.is_inference is True

    def test_timestamp_auto_set(self):
        from app.agent.state import EvidenceItem
        ev = EvidenceItem(source="test", resource="res", observation="obs")
        assert isinstance(ev.timestamp, datetime)


class TestToolResult:
    def test_creation(self):
        from app.agent.state import ToolResult
        tr = ToolResult(
            tool_name="get_pods",
            status="success",
            command_type="read",
            namespace="employment-management",
            stdout="pod/my-pod   Running",
            exit_code=0,
            duration=0.3,
        )
        assert tr.tool_name == "get_pods"
        assert tr.exit_code == 0

    def test_error_result(self):
        from app.agent.state import ToolResult
        tr = ToolResult(
            tool_name="get_pods",
            status="error",
            command_type="read",
            error="kubectl: command not found",
        )
        assert tr.status == "error"
        assert tr.error


class TestRemediationAction:
    def test_requires_approval_default(self):
        from app.agent.state import RemediationAction, RiskLevel
        action = RemediationAction(
            action="Restart pod",
            reason="Pod is crash-looping",
            expected_result="Pod transitions to Running",
            risk=RiskLevel.MEDIUM,
            rollback="Delete new pod; previous will restart",
        )
        assert action.approval_required is True

    def test_remediation_id_generated(self):
        from app.agent.state import RemediationAction, RiskLevel
        action = RemediationAction(
            action="Update image",
            reason="Wrong tag",
            expected_result="Pod pulls correct image",
            risk=RiskLevel.LOW,
            rollback="Revert image tag",
        )
        uuid.UUID(action.remediation_id)  # raises if invalid


class TestApprovalRecord:
    def test_default_pending(self):
        from app.agent.state import ApprovalRecord, ApprovalStatus
        record = ApprovalRecord(request_id="req-123")
        assert record.status == ApprovalStatus.PENDING

    def test_approval_id_generated(self):
        from app.agent.state import ApprovalRecord
        record = ApprovalRecord(request_id="req-456")
        uuid.UUID(record.approval_id)


class TestRootCauseAnalysis:
    def test_creation(self):
        from app.agent.state import RootCauseAnalysis, ConfidenceLevel, RiskLevel
        rca = RootCauseAnalysis(
            incident_status="ACTIVE",
            affected_resource="pod/my-app",
            root_cause="Invalid readiness probe",
            confidence=ConfidenceLevel.HIGH,
            reasoning_summary="The readiness probe is hitting a non-existent endpoint.",
        )
        assert rca.confidence == ConfidenceLevel.HIGH
        assert rca.alternative_causes == []

    def test_low_confidence(self):
        from app.agent.state import RootCauseAnalysis, ConfidenceLevel, RiskLevel
        rca = RootCauseAnalysis(
            incident_status="UNKNOWN",
            affected_resource="unknown",
            root_cause="Insufficient evidence to determine root cause",
            confidence=ConfidenceLevel.INSUFFICIENT,
            reasoning_summary="Not enough data was collected.",
        )
        assert rca.confidence == ConfidenceLevel.INSUFFICIENT
