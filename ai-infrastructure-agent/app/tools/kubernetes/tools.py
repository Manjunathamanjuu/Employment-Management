"""Read-only Kubernetes diagnostic tools.

All tools use kubectl with explicit argument arrays (never shell=True).
Only allowlisted verbs (get, describe, logs) are permitted.
Destructive operations are blocked at the validation layer.

Default namespace: employment-management
"""

from __future__ import annotations

from typing import Optional

from app.agent.state import ToolResult
from app.config import settings
from app.tools.base import (
    BaseTool,
    validate_k8s_name,
    validate_k8s_namespace,
    validate_kubectl_verb,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ns(namespace: Optional[str]) -> str:
    """Return the namespace to use, defaulting to configured namespace."""
    return namespace or settings.kubernetes_namespace


def _context_args(context: Optional[str]) -> list[str]:
    """Return --context flag if a kubeconfig context is specified."""
    if context:
        return ["--context", context]
    return []


# ---------------------------------------------------------------------------
# Pod tools
# ---------------------------------------------------------------------------


class GetPods(BaseTool):
    """List pods in a namespace."""

    tool_name = "get_pods"

    def execute(
        self,
        namespace: Optional[str] = None,
        context: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        ns = validate_k8s_namespace(_ns(namespace))
        validate_kubectl_verb("get")
        cmd = (
            ["kubectl", "get", "pods", "-n", ns, "-o", "wide"]
            + _context_args(context)
        )
        return self._run_subprocess(cmd, command_type="read", namespace=ns)


class DescribePod(BaseTool):
    """Describe a specific pod."""

    tool_name = "describe_pod"

    def execute(
        self,
        pod_name: str,
        namespace: Optional[str] = None,
        context: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        ns = validate_k8s_namespace(_ns(namespace))
        name = validate_k8s_name(pod_name, "pod_name")
        validate_kubectl_verb("describe")
        cmd = (
            ["kubectl", "describe", "pod", name, "-n", ns]
            + _context_args(context)
        )
        return self._run_subprocess(cmd, command_type="read", resource=name, namespace=ns)


class GetPodLogs(BaseTool):
    """Retrieve logs from a pod container."""

    tool_name = "get_pod_logs"

    def execute(
        self,
        pod_name: str,
        namespace: Optional[str] = None,
        container: Optional[str] = None,
        tail_lines: int = 100,
        previous: bool = False,
        context: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        ns = validate_k8s_namespace(_ns(namespace))
        name = validate_k8s_name(pod_name, "pod_name")
        validate_kubectl_verb("logs")

        # Validate tail_lines to prevent injection via integer overflow
        if not isinstance(tail_lines, int) or tail_lines < 1 or tail_lines > 10000:
            tail_lines = 100

        cmd = ["kubectl", "logs", name, "-n", ns, f"--tail={tail_lines}"]
        if container:
            container = validate_k8s_name(container, "container")
            cmd += ["-c", container]
        if previous:
            cmd.append("--previous")
        cmd += _context_args(context)

        return self._run_subprocess(cmd, command_type="read", resource=name, namespace=ns)


class GetEvents(BaseTool):
    """List Kubernetes events in a namespace, sorted by time."""

    tool_name = "get_events"

    def execute(
        self,
        namespace: Optional[str] = None,
        context: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        ns = validate_k8s_namespace(_ns(namespace))
        validate_kubectl_verb("get")
        cmd = (
            ["kubectl", "get", "events", "-n", ns,
             "--sort-by=.lastTimestamp"]
            + _context_args(context)
        )
        return self._run_subprocess(cmd, command_type="read", namespace=ns)


# ---------------------------------------------------------------------------
# Deployment tools
# ---------------------------------------------------------------------------


class GetDeployment(BaseTool):
    """List or get a specific deployment."""

    tool_name = "get_deployment"

    def execute(
        self,
        deployment_name: Optional[str] = None,
        namespace: Optional[str] = None,
        context: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        ns = validate_k8s_namespace(_ns(namespace))
        validate_kubectl_verb("get")
        cmd = ["kubectl", "get", "deployments", "-n", ns]
        if deployment_name:
            name = validate_k8s_name(deployment_name, "deployment_name")
            cmd[2] = "deployment"
            cmd.append(name)
        cmd += _context_args(context)
        return self._run_subprocess(
            cmd, command_type="read",
            resource=deployment_name, namespace=ns,
        )


class DescribeDeployment(BaseTool):
    """Describe a specific deployment."""

    tool_name = "describe_deployment"

    def execute(
        self,
        deployment_name: str,
        namespace: Optional[str] = None,
        context: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        ns = validate_k8s_namespace(_ns(namespace))
        name = validate_k8s_name(deployment_name, "deployment_name")
        validate_kubectl_verb("describe")
        cmd = (
            ["kubectl", "describe", "deployment", name, "-n", ns]
            + _context_args(context)
        )
        return self._run_subprocess(cmd, command_type="read", resource=name, namespace=ns)


class GetReplicaSets(BaseTool):
    """List replica sets in a namespace."""

    tool_name = "get_replicasets"

    def execute(
        self,
        namespace: Optional[str] = None,
        context: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        ns = validate_k8s_namespace(_ns(namespace))
        validate_kubectl_verb("get")
        cmd = (
            ["kubectl", "get", "replicasets", "-n", ns]
            + _context_args(context)
        )
        return self._run_subprocess(cmd, command_type="read", namespace=ns)


# ---------------------------------------------------------------------------
# Service / networking tools
# ---------------------------------------------------------------------------


class GetService(BaseTool):
    """List or get a specific service."""

    tool_name = "get_service"

    def execute(
        self,
        service_name: Optional[str] = None,
        namespace: Optional[str] = None,
        context: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        ns = validate_k8s_namespace(_ns(namespace))
        validate_kubectl_verb("get")
        cmd = ["kubectl", "get", "services", "-n", ns]
        if service_name:
            name = validate_k8s_name(service_name, "service_name")
            cmd[2] = "service"
            cmd.append(name)
        cmd += _context_args(context)
        return self._run_subprocess(
            cmd, command_type="read",
            resource=service_name, namespace=ns,
        )


class DescribeService(BaseTool):
    """Describe a specific service."""

    tool_name = "describe_service"

    def execute(
        self,
        service_name: str,
        namespace: Optional[str] = None,
        context: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        ns = validate_k8s_namespace(_ns(namespace))
        name = validate_k8s_name(service_name, "service_name")
        validate_kubectl_verb("describe")
        cmd = (
            ["kubectl", "describe", "service", name, "-n", ns]
            + _context_args(context)
        )
        return self._run_subprocess(cmd, command_type="read", resource=name, namespace=ns)


class GetEndpointSlices(BaseTool):
    """List endpoint slices in a namespace."""

    tool_name = "get_endpointslices"

    def execute(
        self,
        namespace: Optional[str] = None,
        context: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        ns = validate_k8s_namespace(_ns(namespace))
        validate_kubectl_verb("get")
        cmd = (
            ["kubectl", "get", "endpointslices", "-n", ns]
            + _context_args(context)
        )
        return self._run_subprocess(cmd, command_type="read", namespace=ns)


# ---------------------------------------------------------------------------
# Gateway API tools
# ---------------------------------------------------------------------------


class GetGateway(BaseTool):
    """List or get a Gateway resource."""

    tool_name = "get_gateway"

    def execute(
        self,
        gateway_name: Optional[str] = None,
        namespace: Optional[str] = None,
        context: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        ns = validate_k8s_namespace(_ns(namespace))
        validate_kubectl_verb("get")
        cmd = ["kubectl", "get", "gateways", "-n", ns]
        if gateway_name:
            name = validate_k8s_name(gateway_name, "gateway_name")
            cmd[2] = "gateway"
            cmd.append(name)
        cmd += _context_args(context)
        return self._run_subprocess(
            cmd, command_type="read",
            resource=gateway_name, namespace=ns,
        )


class DescribeGateway(BaseTool):
    """Describe a specific Gateway resource."""

    tool_name = "describe_gateway"

    def execute(
        self,
        gateway_name: str,
        namespace: Optional[str] = None,
        context: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        ns = validate_k8s_namespace(_ns(namespace))
        name = validate_k8s_name(gateway_name, "gateway_name")
        validate_kubectl_verb("describe")
        cmd = (
            ["kubectl", "describe", "gateway", name, "-n", ns]
            + _context_args(context)
        )
        return self._run_subprocess(cmd, command_type="read", resource=name, namespace=ns)


class GetHTTPRoute(BaseTool):
    """List or get an HTTPRoute resource."""

    tool_name = "get_httproute"

    def execute(
        self,
        route_name: Optional[str] = None,
        namespace: Optional[str] = None,
        context: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        ns = validate_k8s_namespace(_ns(namespace))
        validate_kubectl_verb("get")
        cmd = ["kubectl", "get", "httproutes", "-n", ns]
        if route_name:
            name = validate_k8s_name(route_name, "route_name")
            cmd[2] = "httproute"
            cmd.append(name)
        cmd += _context_args(context)
        return self._run_subprocess(
            cmd, command_type="read",
            resource=route_name, namespace=ns,
        )


class DescribeHTTPRoute(BaseTool):
    """Describe a specific HTTPRoute resource."""

    tool_name = "describe_httproute"

    def execute(
        self,
        route_name: str,
        namespace: Optional[str] = None,
        context: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        ns = validate_k8s_namespace(_ns(namespace))
        name = validate_k8s_name(route_name, "route_name")
        validate_kubectl_verb("describe")
        cmd = (
            ["kubectl", "describe", "httproute", name, "-n", ns]
            + _context_args(context)
        )
        return self._run_subprocess(cmd, command_type="read", resource=name, namespace=ns)


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

KUBERNETES_TOOLS: dict[str, type[BaseTool]] = {
    "get_pods": GetPods,
    "describe_pod": DescribePod,
    "get_pod_logs": GetPodLogs,
    "get_events": GetEvents,
    "get_deployment": GetDeployment,
    "describe_deployment": DescribeDeployment,
    "get_replicasets": GetReplicaSets,
    "get_service": GetService,
    "describe_service": DescribeService,
    "get_endpointslices": GetEndpointSlices,
    "get_gateway": GetGateway,
    "describe_gateway": DescribeGateway,
    "get_httproute": GetHTTPRoute,
    "describe_httproute": DescribeHTTPRoute,
}


def get_kubernetes_tool(tool_name: str, timeout: int = 30) -> BaseTool:
    """Factory: return an instantiated Kubernetes tool by name."""
    cls = KUBERNETES_TOOLS.get(tool_name)
    if cls is None:
        raise ValueError(
            f"Unknown Kubernetes tool: {tool_name!r}. "
            f"Available: {sorted(KUBERNETES_TOOLS.keys())}"
        )
    return cls(timeout=timeout)
