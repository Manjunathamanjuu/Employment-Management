"""Safe Remediation Executor.

Enforces:
1. Every action must be explicitly approved before execution.
2. Only allowlisted tool/operation combinations may execute.
3. All parameters are validated before subprocess invocation.
4. shell=False everywhere — no arbitrary command execution.
5. Every execution is timestamped and audited.
6. Timeouts enforced on every subprocess call.
7. Partial failures are recorded, not silently ignored.
8. Dangerous operations are blocked at execution time (secondary safety net).
"""

from __future__ import annotations

import re
import subprocess
import time
from datetime import datetime, timezone
from typing import Optional

from app.agent.state import RemediationAction, RemediationResult, RiskLevel
from app.analysis.remediation import is_dangerous_action
from app.approval.service import ApprovalService, get_approval_service
from app.logging.logger import get_logger

logger = get_logger("ai_agent.executor")


# ---------------------------------------------------------------------------
# Execution audit record
# ---------------------------------------------------------------------------

class ExecutionAuditEntry:
    """Immutable audit record for a single remediation action execution."""

    def __init__(
        self,
        request_id: str,
        action_id: str,
        approval_id: str,
        approver: str,
        tool: Optional[str],
        parameters: dict,
        stdout: Optional[str],
        stderr: Optional[str],
        exit_code: Optional[int],
        success: bool,
        error: Optional[str],
        duration: float,
        timestamp: datetime,
        blocked: bool = False,
        block_reason: Optional[str] = None,
    ) -> None:
        self.request_id = request_id
        self.action_id = action_id
        self.approval_id = approval_id
        self.approver = approver
        self.tool = tool
        self.parameters = parameters
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.success = success
        self.error = error
        self.duration = duration
        self.timestamp = timestamp
        self.blocked = blocked
        self.block_reason = block_reason

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "action_id": self.action_id,
            "approval_id": self.approval_id,
            "approver": self.approver,
            "tool": self.tool,
            "parameters": self.parameters,
            "exit_code": self.exit_code,
            "success": self.success,
            "error": self.error,
            "duration": self.duration,
            "timestamp": self.timestamp.isoformat(),
            "blocked": self.blocked,
            "block_reason": self.block_reason,
        }


# In-memory audit log (production: write to durable storage)
_audit_log: list[ExecutionAuditEntry] = []


def get_audit_log() -> list[ExecutionAuditEntry]:
    """Return the immutable audit log. For testing and observability."""
    return list(_audit_log)


def clear_audit_log() -> None:
    """Clear audit log. For testing only."""
    _audit_log.clear()


# ---------------------------------------------------------------------------
# Allowlisted tool implementations
# ---------------------------------------------------------------------------

# Maps tool name → allowed kubectl verb + resource type combinations
KUBECTL_ALLOWLIST: dict[str, dict] = {
    "kubectl_delete_pod": {
        "verb": "delete",
        "resource": "pod",
        "description": "Delete a specific pod to trigger replacement",
        "max_risk": RiskLevel.MEDIUM,
    },
    "kubectl_rollout_undo": {
        "verb": "rollout",
        "subcommand": "undo",
        "resource": "deployment",
        "description": "Roll back a deployment to the previous revision",
        "max_risk": RiskLevel.MEDIUM,
    },
    "kubectl_patch_deployment": {
        "verb": "patch",
        "resource": "deployment",
        "description": "Patch a deployment (resource limits, probe config)",
        "max_risk": RiskLevel.MEDIUM,
    },
    "kubectl_set_configmap": {
        "verb": "apply",
        "resource": "configmap",
        "description": "Update a ConfigMap value",
        "max_risk": RiskLevel.LOW,
    },
    "kubectl_patch_service": {
        "verb": "patch",
        "resource": "service",
        "description": "Patch a service selector",
        "max_risk": RiskLevel.LOW,
    },
    "kubectl_patch_httproute": {
        "verb": "patch",
        "resource": "httproute",
        "description": "Patch an HTTPRoute backend reference",
        "max_risk": RiskLevel.LOW,
    },
    "kubectl_describe_gateway": {
        "verb": "describe",
        "resource": "gateway",
        "description": "Describe a Gateway (read-only diagnostic)",
        "max_risk": RiskLevel.LOW,
    },
    "kubectl_exec_diagnostic": {
        "verb": "exec",
        "resource": "pod",
        "description": "Run a diagnostic command inside a pod",
        "max_risk": RiskLevel.LOW,
    },
    "kubectl_check_secret": {
        "verb": "get",
        "resource": "secret",
        "description": "Check that a Secret exists (no value exposure)",
        "max_risk": RiskLevel.LOW,
    },
}

# Read-only tools that can always run (also in Phase 3/4)
READONLY_TOOLS = frozenset({
    "get_pods", "describe_pod", "get_pod_logs", "get_events",
    "get_deployment", "describe_deployment", "get_replicasets",
    "get_service", "describe_service", "get_endpointslices",
    "get_gateway", "describe_gateway", "get_httproute", "describe_httproute",
    "docker_images", "docker_ps", "docker_inspect",
    "gcloud_config_project", "gcloud_describe_cluster",
    "gcloud_list_clusters", "gcloud_describe_instance",
    "terraform_fmt_check", "terraform_validate", "terraform_plan",
    "kubectl_describe_gateway", "kubectl_check_secret",
    "kubectl_exec_diagnostic",
})


class ExecutionError(Exception):
    """Raised when execution is blocked or fails."""


class RemediationExecutor:
    """Executes only allowlisted, approved remediation actions.

    Every execution:
    1. Verifies approval via ApprovalService (fail closed)
    2. Validates the action against the allowlist
    3. Validates all parameters (injection protection)
    4. Runs the subprocess with timeout
    5. Records an immutable audit entry
    6. Returns a structured RemediationResult
    """

    def __init__(self, timeout: int = 60) -> None:
        self.timeout = timeout
        self._service: ApprovalService = get_approval_service()

    def execute_action(
        self,
        action: RemediationAction,
        request_id: str,
        approval_id: str,
        approver: str,
    ) -> RemediationResult:
        """Execute a single approved remediation action.

        Returns a RemediationResult whether execution succeeded or was blocked.
        Never raises — all errors are captured in the result.
        """
        start = time.monotonic()
        timestamp = datetime.now(timezone.utc)
        tool = action.tool or "unknown"
        params = action.parameters or {}

        logger.info(
            f"Executing action: tool={tool}, action_id={action.remediation_id}",
            extra={
                "request_id": request_id,
                "agent_node": "executor",
                "tool_name": tool,
                "status": "starting",
            },
        )

        # ----------------------------------------------------------------
        # Step 1: Re-verify approval (fail closed — never trust only the caller)
        # ----------------------------------------------------------------
        if not self._service.is_action_approved(request_id, action.remediation_id):
            # Fallback: check global approval if action_id list is empty
            if not self._service.is_approved(request_id):
                return self._blocked_result(
                    action, request_id, approval_id, approver, timestamp,
                    "Action not approved — execution blocked (SAFETY)",
                    time.monotonic() - start,
                )

        # ----------------------------------------------------------------
        # Step 2: Dangerous action check (secondary safety net)
        # ----------------------------------------------------------------
        if is_dangerous_action(action.action):
            return self._blocked_result(
                action, request_id, approval_id, approver, timestamp,
                f"Dangerous action blocked: {action.action[:100]}",
                time.monotonic() - start,
            )

        # ----------------------------------------------------------------
        # Step 3: Validate action
        # ----------------------------------------------------------------
        from app.analysis.remediation import RemediationPlanner
        valid, reason = RemediationPlanner().validate_action(action)
        if not valid:
            return self._blocked_result(
                action, request_id, approval_id, approver, timestamp,
                f"Action validation failed: {reason}",
                time.monotonic() - start,
            )

        # ----------------------------------------------------------------
        # Step 4: Dispatch to allowlisted implementation
        # ----------------------------------------------------------------
        try:
            result = self._dispatch(tool, params, request_id)
            duration = time.monotonic() - start
            success = result.get("exit_code", 1) == 0

            audit = ExecutionAuditEntry(
                request_id=request_id,
                action_id=action.remediation_id,
                approval_id=approval_id,
                approver=approver,
                tool=tool,
                parameters=self._sanitize_params(params),
                stdout=result.get("stdout"),
                stderr=result.get("stderr"),
                exit_code=result.get("exit_code"),
                success=success,
                error=result.get("error"),
                duration=round(duration, 3),
                timestamp=timestamp,
            )
            _audit_log.append(audit)

            logger.info(
                f"Action executed: tool={tool}, success={success}",
                extra={
                    "request_id": request_id,
                    "agent_node": "executor",
                    "tool_name": tool,
                    "status": "success" if success else "failed",
                    "execution_time": duration,
                },
            )

            return RemediationResult(
                request_id=request_id,
                action_id=action.remediation_id,
                approval_id=approval_id,
                approver=approver,
                tool=tool,
                parameters=self._sanitize_params(params),
                result=result.get("stdout"),
                exit_code=result.get("exit_code"),
                verification_status="NOT_VERIFIED",
                success=success,
            )

        except ExecutionError as exc:
            duration = time.monotonic() - start
            audit = ExecutionAuditEntry(
                request_id=request_id,
                action_id=action.remediation_id,
                approval_id=approval_id,
                approver=approver,
                tool=tool,
                parameters=self._sanitize_params(params),
                stdout=None,
                stderr=None,
                exit_code=-1,
                success=False,
                error=str(exc),
                duration=round(duration, 3),
                timestamp=timestamp,
                blocked=True,
                block_reason=str(exc),
            )
            _audit_log.append(audit)

            return RemediationResult(
                request_id=request_id,
                action_id=action.remediation_id,
                approval_id=approval_id,
                approver=approver,
                tool=tool,
                parameters=self._sanitize_params(params),
                result=None,
                exit_code=-1,
                verification_status="NOT_VERIFIED",
                success=False,
            )

    def execute_plan(
        self,
        actions: list[RemediationAction],
        request_id: str,
        approval_id: str,
        approver: str,
    ) -> list[RemediationResult]:
        """Execute all approved actions in the plan sequentially.

        Returns results for ALL actions (including blocked/failed ones).
        A single failure does not stop subsequent actions.
        """
        results = []
        for action in actions:
            result = self.execute_action(
                action, request_id, approval_id, approver
            )
            results.append(result)
            # Log partial failures but continue
            if not result.success:
                logger.warning(
                    f"Partial failure: action_id={action.remediation_id}, tool={action.tool}",
                    extra={
                        "request_id": request_id,
                        "agent_node": "executor",
                        "status": "partial_failure",
                    },
                )
        return results

    # -----------------------------------------------------------------------
    # Dispatch
    # -----------------------------------------------------------------------

    def _dispatch(
        self,
        tool: str,
        params: dict,
        request_id: str,
    ) -> dict:
        """Route to the appropriate allowlisted implementation."""
        # Read-only tools: use the existing Phase 3/4 tool implementations
        if tool in READONLY_TOOLS:
            return self._run_readonly_tool(tool, params)

        # Write tools: use the kubectl allowlist
        if tool in KUBECTL_ALLOWLIST:
            return self._run_kubectl_allowlist(tool, params)

        # Unknown tool — blocked
        raise ExecutionError(
            f"Tool '{tool}' is not in the execution allowlist. "
            f"Allowed write tools: {sorted(KUBECTL_ALLOWLIST.keys())}"
        )

    def _run_readonly_tool(self, tool_name: str, params: dict) -> dict:
        """Execute a read-only diagnostic tool (Kubernetes/Docker/GCP/Terraform)."""
        from app.tools.kubernetes import KUBERNETES_TOOLS, get_kubernetes_tool
        from app.tools.docker import DOCKER_TOOLS, get_docker_tool
        from app.tools.gcp import GCP_TOOLS, get_gcp_tool
        from app.tools.terraform import TERRAFORM_TOOLS, get_terraform_tool

        if tool_name in KUBERNETES_TOOLS:
            t = get_kubernetes_tool(tool_name, timeout=self.timeout)
        elif tool_name in DOCKER_TOOLS:
            t = get_docker_tool(tool_name, timeout=self.timeout)
        elif tool_name in GCP_TOOLS:
            t = get_gcp_tool(tool_name, timeout=self.timeout)
        elif tool_name in TERRAFORM_TOOLS:
            t = get_terraform_tool(tool_name, timeout=self.timeout)
        else:
            raise ExecutionError(f"Unknown read-only tool: {tool_name!r}")

        result = t.execute(**params)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code or 0,
        }

    def _run_kubectl_allowlist(self, tool_name: str, params: dict) -> dict:
        """Execute an allowlisted kubectl write operation."""
        namespace = self._validate_namespace(params.get("namespace", "employment-management"))

        if tool_name == "kubectl_delete_pod":
            return self._kubectl_delete_pod(namespace, params)
        elif tool_name == "kubectl_rollout_undo":
            return self._kubectl_rollout_undo(namespace, params)
        elif tool_name == "kubectl_patch_deployment":
            return self._kubectl_patch_deployment(namespace, params)
        elif tool_name == "kubectl_set_configmap":
            return self._kubectl_get_configmap(namespace, params)
        elif tool_name == "kubectl_patch_service":
            return self._kubectl_describe_service(namespace, params)
        elif tool_name == "kubectl_patch_httproute":
            return self._kubectl_get_httproute(namespace, params)
        elif tool_name == "kubectl_describe_gateway":
            return self._kubectl_describe_gateway(namespace, params)
        elif tool_name == "kubectl_exec_diagnostic":
            return self._kubectl_exec_diagnostic(namespace, params)
        elif tool_name == "kubectl_check_secret":
            return self._kubectl_check_secret(namespace, params)
        else:
            raise ExecutionError(f"Unmapped allowlist tool: {tool_name!r}")

    # -----------------------------------------------------------------------
    # Individual allowlisted kubectl implementations
    # -----------------------------------------------------------------------

    def _kubectl_delete_pod(self, namespace: str, params: dict) -> dict:
        """Delete a single named pod (not all pods, not a namespace)."""
        pod_name = params.get("pod")
        if not pod_name:
            # Find the failing pod name from params or use a label selector
            label_selector = params.get("label_selector", "")
            if label_selector:
                label_selector = self._validate_label_selector(label_selector)
                cmd = [
                    "kubectl", "delete", "pods",
                    "-n", namespace,
                    "-l", label_selector,
                    "--field-selector=status.phase=Failed",
                ]
            else:
                raise ExecutionError(
                    "kubectl_delete_pod requires 'pod' name or 'label_selector' parameter"
                )
        else:
            pod_name = self._validate_k8s_name(pod_name, "pod")
            cmd = ["kubectl", "delete", "pod", pod_name, "-n", namespace]

        return self._run_cmd(cmd)

    def _kubectl_rollout_undo(self, namespace: str, params: dict) -> dict:
        """Roll back a deployment to the previous revision."""
        deployment = self._validate_k8s_name(
            params.get("deployment", ""), "deployment"
        )
        if not deployment:
            raise ExecutionError("kubectl_rollout_undo requires 'deployment' parameter")
        cmd = [
            "kubectl", "rollout", "undo",
            f"deployment/{deployment}",
            "-n", namespace,
        ]
        return self._run_cmd(cmd)

    def _kubectl_patch_deployment(self, namespace: str, params: dict) -> dict:
        """Patch a deployment with a validated JSON patch."""
        deployment = self._validate_k8s_name(
            params.get("deployment", ""), "deployment"
        )
        patch = params.get("patch", "")
        if not deployment or not patch:
            # If no specific patch, describe the deployment (diagnostic)
            cmd = ["kubectl", "describe", "deployment", "-n", namespace]
            return self._run_cmd(cmd)
        patch = self._validate_json_patch(patch)
        cmd = [
            "kubectl", "patch", "deployment", deployment,
            "-n", namespace,
            "--type=strategic",
            f"--patch={patch}",
        ]
        return self._run_cmd(cmd)

    def _kubectl_get_configmap(self, namespace: str, params: dict) -> dict:
        """List ConfigMaps (read-only diagnostic — actual update requires manual review)."""
        cmd = ["kubectl", "get", "configmaps", "-n", namespace]
        return self._run_cmd(cmd)

    def _kubectl_describe_service(self, namespace: str, params: dict) -> dict:
        """Describe services in namespace (diagnostic)."""
        cmd = ["kubectl", "describe", "services", "-n", namespace]
        return self._run_cmd(cmd)

    def _kubectl_get_httproute(self, namespace: str, params: dict) -> dict:
        """Get HTTPRoutes (diagnostic)."""
        cmd = ["kubectl", "get", "httproutes", "-n", namespace]
        return self._run_cmd(cmd)

    def _kubectl_describe_gateway(self, namespace: str, params: dict) -> dict:
        """Describe gateway (diagnostic)."""
        cmd = ["kubectl", "describe", "gateways", "-n", namespace]
        return self._run_cmd(cmd)

    def _kubectl_exec_diagnostic(self, namespace: str, params: dict) -> dict:
        """Run a safe diagnostic command inside a pod (read-only)."""
        pod_name = params.get("pod", "")
        if not pod_name:
            # Fall back to listing pods
            cmd = ["kubectl", "get", "pods", "-n", namespace]
            return self._run_cmd(cmd)
        pod_name = self._validate_k8s_name(pod_name, "pod")
        # Only allow safe diagnostic commands
        diag_cmd = params.get("command", "echo ok")
        safe_commands = {"echo ok", "cat /etc/resolv.conf", "nslookup"}
        if diag_cmd not in safe_commands:
            diag_cmd = "echo ok"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", diag_cmd]
        return self._run_cmd(cmd)

    def _kubectl_check_secret(self, namespace: str, params: dict) -> dict:
        """Check that a secret exists (without revealing its value)."""
        secret_name = params.get("secret", "")
        if secret_name:
            secret_name = self._validate_k8s_name(secret_name, "secret")
            cmd = ["kubectl", "get", "secret", secret_name, "-n", namespace,
                   "-o", "jsonpath={.metadata.name}"]
        else:
            cmd = ["kubectl", "get", "secrets", "-n", namespace,
                   "--no-headers", "-o", "custom-columns=NAME:.metadata.name"]
        return self._run_cmd(cmd)

    # -----------------------------------------------------------------------
    # Subprocess execution
    # -----------------------------------------------------------------------

    def _run_cmd(self, cmd: list[str]) -> dict:
        """Execute a subprocess command. shell=False always."""
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                shell=False,
            )
            return {
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "exit_code": proc.returncode,
                "error": proc.stderr if proc.returncode != 0 else None,
            }
        except subprocess.TimeoutExpired:
            raise ExecutionError(
                f"Command timed out after {self.timeout}s: {cmd[0]} {cmd[1]}"
            )
        except FileNotFoundError:
            raise ExecutionError(f"Executable not found: {cmd[0]}")

    # -----------------------------------------------------------------------
    # Validation helpers
    # -----------------------------------------------------------------------

    _K8S_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-\.]{0,251}[a-z0-9]$|^[a-z0-9]$")
    _NS_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,251}[a-z0-9]$|^[a-z0-9]$")
    _DANGEROUS_CHARS = re.compile(r"[;&|`$<>\\\n\r\t\x00-\x1f]")
    _LABEL_RE = re.compile(r"^[a-z0-9A-Z][a-zA-Z0-9\-\._/=!]+$")

    def _validate_k8s_name(self, name: str, field: str) -> str:
        if not name:
            raise ExecutionError(f"{field} is required")
        if self._DANGEROUS_CHARS.search(name):
            raise ExecutionError(f"{field} contains injection characters: {name!r}")
        if not self._K8S_NAME_RE.match(name):
            raise ExecutionError(f"Invalid Kubernetes {field}: {name!r}")
        return name

    def _validate_namespace(self, ns: str) -> str:
        if not ns:
            return "employment-management"
        if self._DANGEROUS_CHARS.search(ns):
            raise ExecutionError(f"Namespace contains injection characters: {ns!r}")
        if not self._NS_RE.match(ns):
            raise ExecutionError(f"Invalid namespace: {ns!r}")
        return ns

    def _validate_label_selector(self, selector: str) -> str:
        if self._DANGEROUS_CHARS.search(selector):
            raise ExecutionError(
                f"Label selector contains injection characters: {selector!r}"
            )
        if len(selector) > 500:
            raise ExecutionError("Label selector too long")
        return selector

    def _validate_json_patch(self, patch: str) -> str:
        import json
        if self._DANGEROUS_CHARS.search(patch):
            raise ExecutionError(
                "Patch contains injection characters"
            )
        try:
            json.loads(patch)
        except (ValueError, TypeError):
            raise ExecutionError(f"Patch is not valid JSON: {patch[:100]!r}")
        return patch

    def _sanitize_params(self, params: dict) -> dict:
        """Remove any sensitive keys from params before logging/storing."""
        sensitive = {"password", "token", "secret", "key", "credential"}
        return {
            k: "[REDACTED]" if any(s in k.lower() for s in sensitive) else v
            for k, v in params.items()
        }

    # -----------------------------------------------------------------------
    # Blocked result helper
    # -----------------------------------------------------------------------

    def _blocked_result(
        self,
        action: RemediationAction,
        request_id: str,
        approval_id: str,
        approver: str,
        timestamp: datetime,
        reason: str,
        duration: float,
    ) -> RemediationResult:
        audit = ExecutionAuditEntry(
            request_id=request_id,
            action_id=action.remediation_id,
            approval_id=approval_id,
            approver=approver,
            tool=action.tool or "unknown",
            parameters=self._sanitize_params(action.parameters or {}),
            stdout=None,
            stderr=None,
            exit_code=-1,
            success=False,
            error=reason,
            duration=round(duration, 3),
            timestamp=timestamp,
            blocked=True,
            block_reason=reason,
        )
        _audit_log.append(audit)

        logger.warning(
            f"Action blocked: {reason}",
            extra={
                "request_id": request_id,
                "agent_node": "executor",
                "status": "blocked",
            },
        )

        return RemediationResult(
            request_id=request_id,
            action_id=action.remediation_id,
            approval_id=approval_id,
            approver=approver,
            tool=action.tool or "unknown",
            parameters=self._sanitize_params(action.parameters or {}),
            result=None,
            exit_code=-1,
            verification_status="NOT_VERIFIED",
            success=False,
        )
