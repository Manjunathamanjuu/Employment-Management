"""Base tool interface.

Every infrastructure tool must inherit BaseTool and implement `execute()`.

Safety requirements enforced here:
- All tool names declared in an explicit allowlist.
- All subprocess calls use argument arrays — never shell=True.
- Input parameters validated before execution.
- Timeouts enforced on every subprocess call.
- Secrets never passed through tool parameters.
- Tool output structured as ToolResult for consistent downstream handling.
"""

from __future__ import annotations

import re
import subprocess
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

from app.agent.state import ToolResult
from app.logging.logger import AgentLogger


# ---------------------------------------------------------------------------
# Injection / path-traversal protection
# ---------------------------------------------------------------------------

# Characters that could be used for shell injection or path traversal
_DANGEROUS_CHARS = re.compile(r"[;&|`$<>\\\n\r\t\x00-\x1f]")

# Kubernetes name: lowercase alphanumeric, hyphens, dots, slashes (for pod/name)
_K8S_NAME_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9\-\.\/]{0,251}[a-z0-9])?$")

# Kubernetes namespace pattern
_K8S_NAMESPACE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-]{0,251}[a-z0-9]$|^[a-z0-9]$")

# Allowlisted kubectl subcommands (read-only only)
KUBECTL_ALLOWED_VERBS = frozenset({
    "get",
    "describe",
    "logs",
})

# Blocked kubectl verbs — explicitly denied even if somehow presented
KUBECTL_BLOCKED_VERBS = frozenset({
    "delete",
    "apply",
    "patch",
    "edit",
    "exec",
    "scale",
    "rollout",
    "create",
    "replace",
    "run",
    "expose",
    "set",
    "drain",
    "cordon",
    "uncordon",
    "taint",
    "label",
    "annotate",
    "cp",
    "port-forward",
    "attach",
    "debug",
    "alpha",
    "beta",
})


def validate_k8s_name(name: str, field: str = "resource") -> str:
    """Validate a Kubernetes resource name.

    Raises ValueError on injection characters or invalid format.
    Returns the cleaned name on success.
    """
    if not name or not isinstance(name, str):
        raise ValueError(f"{field} must be a non-empty string")
    name = name.strip()
    if _DANGEROUS_CHARS.search(name):
        raise ValueError(
            f"{field} contains invalid characters: {name!r}"
        )
    if not _K8S_NAME_PATTERN.match(name):
        raise ValueError(
            f"{field} is not a valid Kubernetes name: {name!r}"
        )
    return name


def validate_k8s_namespace(namespace: str) -> str:
    """Validate a Kubernetes namespace name."""
    if not namespace or not isinstance(namespace, str):
        raise ValueError("namespace must be a non-empty string")
    namespace = namespace.strip()
    if _DANGEROUS_CHARS.search(namespace):
        raise ValueError(
            f"namespace contains invalid characters: {namespace!r}"
        )
    if not _K8S_NAMESPACE_PATTERN.match(namespace):
        raise ValueError(
            f"Invalid Kubernetes namespace: {namespace!r}"
        )
    return namespace


def validate_kubectl_verb(verb: str) -> str:
    """Ensure only allowlisted kubectl verbs are used."""
    if verb in KUBECTL_BLOCKED_VERBS:
        raise ValueError(
            f"kubectl verb '{verb}' is explicitly blocked. "
            f"Allowed verbs: {sorted(KUBECTL_ALLOWED_VERBS)}"
        )
    if verb not in KUBECTL_ALLOWED_VERBS:
        raise ValueError(
            f"kubectl verb '{verb}' is not in the allowlist. "
            f"Allowed verbs: {sorted(KUBECTL_ALLOWED_VERBS)}"
        )
    return verb


# ---------------------------------------------------------------------------
# Base tool
# ---------------------------------------------------------------------------


class BaseTool(ABC):
    """Abstract base for all infrastructure tools."""

    #: Subclasses must declare their tool name
    tool_name: str = "base"

    def __init__(
        self,
        timeout: int = 30,
        logger: Optional[AgentLogger] = None,
        request_id: Optional[str] = None,
    ) -> None:
        self.timeout = timeout
        self.logger = logger or AgentLogger(
            f"ai_agent.tools.{self.tool_name}",
            request_id=request_id,
        )

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool and return a structured ToolResult."""
        ...

    def _run_subprocess(
        self,
        cmd: list[str],
        command_type: str = "read",
        resource: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> ToolResult:
        """Run a subprocess with timeout, capture output, return ToolResult.

        Command must always be an argument list. shell is explicitly disabled.
        """
        start = time.monotonic()
        timestamp = datetime.now(timezone.utc)

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                shell=False,
            )
            duration = time.monotonic() - start

            status = "success" if proc.returncode == 0 else "error"
            result = ToolResult(
                tool_name=self.tool_name,
                status=status,
                command_type=command_type,
                resource=resource,
                namespace=namespace,
                stdout=proc.stdout,
                stderr=proc.stderr,
                exit_code=proc.returncode,
                duration=round(duration, 3),
                timestamp=timestamp,
                error=proc.stderr if proc.returncode != 0 else None,
            )

            self.logger.tool_call(
                tool_name=self.tool_name,
                status=status,
                execution_time=duration,
            )
            return result

        except subprocess.TimeoutExpired:
            duration = time.monotonic() - start
            self.logger.error(
                f"Tool {self.tool_name} timed out after {self.timeout}s",
                status="timeout",
                execution_time=duration,
            )
            return ToolResult(
                tool_name=self.tool_name,
                status="timeout",
                command_type=command_type,
                resource=resource,
                namespace=namespace,
                exit_code=-1,
                duration=round(duration, 3),
                timestamp=timestamp,
                error=f"Command timed out after {self.timeout} seconds",
            )

        except FileNotFoundError as exc:
            duration = time.monotonic() - start
            self.logger.error(
                f"Tool {self.tool_name} executable not found: {cmd[0]}",
                status="not_found",
                execution_time=duration,
            )
            return ToolResult(
                tool_name=self.tool_name,
                status="not_found",
                command_type=command_type,
                resource=resource,
                namespace=namespace,
                exit_code=-1,
                duration=round(duration, 3),
                timestamp=timestamp,
                error=f"Executable not found: {cmd[0]}",
            )

        except Exception as exc:
            duration = time.monotonic() - start
            self.logger.error(
                f"Tool {self.tool_name} unexpected error: {type(exc).__name__}",
                status="error",
                execution_time=duration,
            )
            return ToolResult(
                tool_name=self.tool_name,
                status="error",
                command_type=command_type,
                resource=resource,
                namespace=namespace,
                exit_code=-1,
                duration=round(duration, 3),
                timestamp=timestamp,
                error=f"Unexpected error: {type(exc).__name__}",
            )
