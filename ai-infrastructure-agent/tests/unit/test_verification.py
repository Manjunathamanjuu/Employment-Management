"""Unit tests for post-remediation verification."""

from __future__ import annotations

import subprocess
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.agent.state import RemediationResult, ToolResult, VerificationResult
from app.verification.verifier import (
    VerificationSnapshot,
    VerificationStatus,
    Verifier,
    _extract_deployment_health,
    _extract_pod_health,
)

pytestmark = pytest.mark.unit

NS = "employment-management"


def _make_proc(stdout: str = "", stderr: str = "", returncode: int = 0):
    m = MagicMock(spec=subprocess.CompletedProcess)
    m.stdout = stdout
    m.stderr = stderr
    m.returncode = returncode
    return m


def _remediation_result(success: bool = True) -> RemediationResult:
    return RemediationResult(
        request_id=str(uuid.uuid4()),
        action_id=str(uuid.uuid4()),
        approval_id=str(uuid.uuid4()),
        approver="ops-team",
        tool="kubectl_delete_pod",
        parameters={"namespace": NS},
        exit_code=0 if success else 1,
        verification_status="NOT_VERIFIED",
        success=success,
    )


def _healthy_pod_stdout() -> str:
    return (
        "NAME                               READY   STATUS    RESTARTS   AGE\n"
        "employment-management-abc123   1/1     Running   0          2m"
    )


def _unhealthy_pod_stdout() -> str:
    return (
        "NAME                               READY   STATUS             RESTARTS\n"
        "employment-management-abc123   0/1     CrashLoopBackOff   8"
    )


def _healthy_deploy_stdout() -> str:
    return (
        "NAME                    READY   UP-TO-DATE   AVAILABLE   AGE\n"
        "employment-management   1/1     1            1           5d"
    )


def _unhealthy_deploy_stdout() -> str:
    return (
        "NAME                    READY   UP-TO-DATE   AVAILABLE   AGE\n"
        "employment-management   0/1     1            0           5d"
    )


# ---------------------------------------------------------------------------
# Health signal extraction (unit)
# ---------------------------------------------------------------------------

class TestExtractPodHealth:
    def test_running_pod_is_healthy(self):
        h = _extract_pod_health(_healthy_pod_stdout())
        assert h["healthy"] is True
        assert h["status"] == "Running"

    def test_crashloop_is_unhealthy(self):
        h = _extract_pod_health(_unhealthy_pod_stdout())
        assert h["healthy"] is False
        assert "CrashLoopBackOff" in h["status"]

    def test_imagepullbackoff_is_unhealthy(self):
        h = _extract_pod_health(
            "NAME  READY  STATUS\npod  0/1  ImagePullBackOff  3"
        )
        assert h["healthy"] is False

    def test_pending_is_unhealthy(self):
        h = _extract_pod_health("NAME  READY  STATUS\npod  0/1  Pending  0")
        assert h["healthy"] is False

    def test_empty_output_is_unhealthy(self):
        h = _extract_pod_health("")
        assert h["healthy"] is False

    def test_none_output_is_unhealthy(self):
        h = _extract_pod_health(None)
        assert h["healthy"] is False


class TestExtractDeploymentHealth:
    def test_fully_ready_deployment_healthy(self):
        h = _extract_deployment_health(_healthy_deploy_stdout())
        assert h["healthy"] is True

    def test_zero_ready_deployment_unhealthy(self):
        h = _extract_deployment_health(_unhealthy_deploy_stdout())
        assert h["healthy"] is False

    def test_available_true_is_healthy(self):
        h = _extract_deployment_health("Available: True\nReplicas: 1")
        assert h["healthy"] is True

    def test_available_false_is_unhealthy(self):
        h = _extract_deployment_health("Available: False\nReplicas: 0")
        assert h["healthy"] is False

    def test_empty_output_is_unhealthy(self):
        h = _extract_deployment_health("")
        assert h["healthy"] is False


# ---------------------------------------------------------------------------
# Healthy after remediation → VERIFIED
# ---------------------------------------------------------------------------

class TestHealthyAfterRemediation:
    @patch("subprocess.run")
    def test_verified_when_pods_running(self, mock_run):
        mock_run.return_value = _make_proc(stdout=_healthy_pod_stdout())
        verifier = Verifier(timeout=5, namespace=NS)
        result = verifier.verify(
            before_snapshot=None,
            remediation_results=[_remediation_result(success=True)],
        )
        assert result.verified is True
        assert result.status == VerificationStatus.VERIFIED

    @patch("subprocess.run")
    def test_verified_records_after_state(self, mock_run):
        mock_run.return_value = _make_proc(stdout=_healthy_pod_stdout())
        verifier = Verifier(namespace=NS)
        result = verifier.verify(before_snapshot=None, remediation_results=[])
        assert result.after_state is not None
        assert "Running" in result.after_state or "pods" in result.after_state.lower()

    @patch("subprocess.run")
    def test_verified_has_details(self, mock_run):
        mock_run.return_value = _make_proc(stdout=_healthy_pod_stdout())
        verifier = Verifier(namespace=NS)
        result = verifier.verify(before_snapshot=None, remediation_results=[])
        assert result.details

    @patch("subprocess.run")
    def test_verified_includes_before_state(self, mock_run):
        mock_run.return_value = _make_proc(stdout=_healthy_pod_stdout())
        before = VerificationSnapshot(
            timestamp=datetime.now(timezone.utc),
            pod_health={"healthy": False, "status": "CrashLoopBackOff"},
        )
        verifier = Verifier(namespace=NS)
        result = verifier.verify(
            before_snapshot=before,
            remediation_results=[_remediation_result()],
        )
        assert result.before_state is not None


# ---------------------------------------------------------------------------
# Unhealthy after remediation → REMEDIATION_EXECUTED_BUT_NOT_VERIFIED
# ---------------------------------------------------------------------------

class TestUnhealthyAfterRemediation:
    @patch("subprocess.run")
    def test_still_crashing_after_remediation(self, mock_run):
        mock_run.return_value = _make_proc(stdout=_unhealthy_pod_stdout())
        verifier = Verifier(namespace=NS)
        result = verifier.verify(
            before_snapshot=None,
            remediation_results=[_remediation_result(success=True)],
        )
        assert result.verified is False
        assert result.status in (
            VerificationStatus.FAILED,
            VerificationStatus.NOT_VERIFIED,
            VerificationStatus.PARTIALLY_VERIFIED,
        )

    @patch("subprocess.run")
    def test_not_verified_explicit_status(self, mock_run):
        mock_run.return_value = _make_proc(stdout=_unhealthy_pod_stdout())
        before = VerificationSnapshot(
            timestamp=datetime.now(timezone.utc),
            pod_health={"healthy": False, "status": "CrashLoopBackOff"},
        )
        verifier = Verifier(namespace=NS)
        result = verifier.verify(
            before_snapshot=before,
            remediation_results=[_remediation_result(success=True)],
        )
        assert not result.verified
        assert result.status == VerificationStatus.FAILED

    @patch("subprocess.run")
    def test_details_mention_before_and_after(self, mock_run):
        mock_run.return_value = _make_proc(stdout=_unhealthy_pod_stdout())
        before = VerificationSnapshot(
            timestamp=datetime.now(timezone.utc),
            pod_health={"healthy": False, "status": "CrashLoopBackOff"},
        )
        verifier = Verifier(namespace=NS)
        result = verifier.verify(
            before_snapshot=before,
            remediation_results=[_remediation_result(success=True)],
        )
        assert "Before" in result.details or "before" in result.details.lower()
        assert "After" in result.details or "after" in result.details.lower()


# ---------------------------------------------------------------------------
# Partial recovery
# ---------------------------------------------------------------------------

class TestPartialRecovery:
    @patch("subprocess.run")
    def test_partial_recovery_when_no_before(self, mock_run):
        """Without a before snapshot, treat healthy after state as VERIFIED."""
        mock_run.return_value = _make_proc(stdout=_healthy_pod_stdout())
        verifier = Verifier(namespace=NS)
        result = verifier.verify(
            before_snapshot=None,
            remediation_results=[_remediation_result(success=False)],
        )
        # If pods are running after, regardless of before, it's VERIFIED
        assert result.verified is True

    @patch("subprocess.run")
    def test_partial_with_mixed_results(self, mock_run):
        mock_run.return_value = _make_proc(stdout=_unhealthy_pod_stdout())
        verifier = Verifier(namespace=NS)
        result = verifier.verify(
            before_snapshot=None,
            remediation_results=[
                _remediation_result(success=True),
                _remediation_result(success=False),
            ],
        )
        assert result.verified is False


# ---------------------------------------------------------------------------
# Verification timeout
# ---------------------------------------------------------------------------

class TestVerificationTimeout:
    @patch("subprocess.run")
    def test_timeout_produces_not_verified(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["kubectl"], timeout=30)
        verifier = Verifier(timeout=30, namespace=NS)
        result = verifier.verify(before_snapshot=None, remediation_results=[])
        assert result.verified is False
        assert result.status in (
            VerificationStatus.FAILED,
            VerificationStatus.NOT_VERIFIED,
            VerificationStatus.UNAVAILABLE,
        )

    @patch("subprocess.run")
    def test_timeout_has_details(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["kubectl"], timeout=30)
        verifier = Verifier(namespace=NS)
        result = verifier.verify(before_snapshot=None, remediation_results=[])
        assert result.details


# ---------------------------------------------------------------------------
# Verification failure (kubectl not found / permission denied)
# ---------------------------------------------------------------------------

class TestVerificationFailure:
    @patch("subprocess.run")
    def test_kubectl_not_found_gives_failed(self, mock_run):
        mock_run.side_effect = FileNotFoundError("kubectl not found")
        verifier = Verifier(namespace=NS)
        result = verifier.verify(before_snapshot=None, remediation_results=[])
        assert result.verified is False

    @patch("subprocess.run")
    def test_kubectl_error_exit_code_not_verified(self, mock_run):
        mock_run.return_value = _make_proc(
            stdout="",
            stderr="Error from server: namespace not found",
            returncode=1,
        )
        verifier = Verifier(namespace=NS)
        result = verifier.verify(before_snapshot=None, remediation_results=[])
        assert result.verified is False

    @patch("subprocess.run")
    def test_failed_status_constant(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        verifier = Verifier(namespace=NS)
        result = verifier.verify(
            before_snapshot=None,
            remediation_results=[_remediation_result(success=True)],
        )
        # Should use one of the NOT_VERIFIED-family statuses
        assert result.status in (
            VerificationStatus.FAILED,
            VerificationStatus.NOT_VERIFIED,
        )


# ---------------------------------------------------------------------------
# Verify specific resource
# ---------------------------------------------------------------------------

class TestVerifySpecificResource:
    @patch("subprocess.run")
    def test_pod_running_verified(self, mock_run):
        mock_run.return_value = _make_proc(
            stdout="NAME  READY  STATUS\nmy-pod  1/1  Running  0"
        )
        verifier = Verifier(namespace=NS)
        result = verifier.verify_specific_resource("pod", "my-pod", "Running")
        assert result.verified is True
        assert result.status == VerificationStatus.VERIFIED

    @patch("subprocess.run")
    def test_pod_still_crashing_not_verified(self, mock_run):
        mock_run.return_value = _make_proc(
            stdout="NAME  READY  STATUS\nmy-pod  0/1  CrashLoopBackOff  5"
        )
        verifier = Verifier(namespace=NS)
        result = verifier.verify_specific_resource("pod", "my-pod", "Running")
        assert result.verified is False

    @patch("subprocess.run")
    def test_resource_not_found_not_verified(self, mock_run):
        mock_run.return_value = _make_proc(
            stdout="", stderr="Error: pod not found", returncode=1
        )
        verifier = Verifier(namespace=NS)
        result = verifier.verify_specific_resource("pod", "missing-pod", "Running")
        assert result.verified is False

    def test_unsupported_resource_type_unavailable(self):
        verifier = Verifier(namespace=NS)
        result = verifier.verify_specific_resource("pvc", "my-pvc", "Bound")
        assert result.status == VerificationStatus.UNAVAILABLE
        assert result.verified is False


# ---------------------------------------------------------------------------
# Collect state
# ---------------------------------------------------------------------------

class TestCollectState:
    @patch("subprocess.run")
    def test_collect_state_returns_snapshot(self, mock_run):
        mock_run.return_value = _make_proc(stdout=_healthy_pod_stdout())
        verifier = Verifier(namespace=NS)
        snapshot = verifier.collect_state()
        assert isinstance(snapshot, VerificationSnapshot)
        assert snapshot.timestamp is not None

    @patch("subprocess.run")
    def test_collect_state_extracts_pod_health(self, mock_run):
        mock_run.return_value = _make_proc(stdout=_healthy_pod_stdout())
        verifier = Verifier(namespace=NS)
        snapshot = verifier.collect_state()
        assert snapshot.pod_health.get("healthy") is True

    @patch("subprocess.run")
    def test_collect_state_records_errors(self, mock_run):
        mock_run.return_value = _make_proc(
            stdout="", stderr="Error: namespace not found", returncode=1
        )
        verifier = Verifier(namespace=NS)
        snapshot = verifier.collect_state()
        assert len(snapshot.collection_errors) > 0


# ---------------------------------------------------------------------------
# Verification node integration
# ---------------------------------------------------------------------------

class TestVerificationNode:
    @patch("subprocess.run")
    def test_node_returns_verification_result(self, mock_run):
        mock_run.return_value = _make_proc(stdout=_healthy_pod_stdout())
        from app.agent.nodes import verification
        from app.agent.state import (
            AgentState, ApprovalStatus, InvestigationStatus
        )
        state = AgentState(
            user_request="test",
            approval_status=ApprovalStatus.APPROVED,
        )
        result = verification(state)
        assert "verification_result" in result
        assert isinstance(result["verification_result"], VerificationResult)

    @patch("subprocess.run")
    def test_node_status_is_verifying(self, mock_run):
        mock_run.return_value = _make_proc(stdout=_healthy_pod_stdout())
        from app.agent.nodes import verification
        from app.agent.state import AgentState, ApprovalStatus, InvestigationStatus
        state = AgentState(
            user_request="test",
            approval_status=ApprovalStatus.APPROVED,
        )
        result = verification(state)
        assert result["status"] == InvestigationStatus.VERIFYING

    @patch("subprocess.run")
    def test_node_with_before_tool_results(self, mock_run):
        mock_run.return_value = _make_proc(stdout=_healthy_pod_stdout())
        from app.agent.nodes import verification
        from app.agent.state import AgentState, ApprovalStatus, ToolResult
        state = AgentState(
            user_request="test",
            approval_status=ApprovalStatus.APPROVED,
            tool_results=[
                ToolResult(
                    tool_name="get_pods",
                    status="success",
                    command_type="read",
                    stdout=_unhealthy_pod_stdout(),
                )
            ],
        )
        result = verification(state)
        vr = result["verification_result"]
        assert vr.before_state is not None

    @patch("subprocess.run")
    def test_node_verified_healthy_result(self, mock_run):
        mock_run.return_value = _make_proc(stdout=_healthy_pod_stdout())
        from app.agent.nodes import verification
        from app.agent.state import AgentState, ApprovalStatus
        state = AgentState(
            user_request="test",
            approval_status=ApprovalStatus.APPROVED,
        )
        result = verification(state)
        vr = result["verification_result"]
        assert vr.verified is True
        assert vr.status == VerificationStatus.VERIFIED

    @patch("subprocess.run")
    def test_node_not_verified_when_unhealthy(self, mock_run):
        mock_run.return_value = _make_proc(stdout=_unhealthy_pod_stdout())
        from app.agent.nodes import verification
        from app.agent.state import AgentState, ApprovalStatus
        state = AgentState(
            user_request="test",
            approval_status=ApprovalStatus.APPROVED,
        )
        result = verification(state)
        vr = result["verification_result"]
        assert vr.verified is False


# ---------------------------------------------------------------------------
# No shell=True
# ---------------------------------------------------------------------------

class TestNoShellTrue:
    def test_verifier_never_uses_shell_true(self):
        import inspect, re
        source = inspect.getsource(Verifier._run_kubectl)
        assert not re.search(r"shell\s*=\s*True", source)
        assert re.search(r"shell\s*=\s*False", source)
