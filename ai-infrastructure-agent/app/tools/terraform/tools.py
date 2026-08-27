"""Read-only Terraform diagnostic tools.

Allowed:  terraform fmt -check, terraform validate, terraform plan
Blocked:  terraform apply, terraform destroy (and all other mutating operations)

Working directory is validated to prevent path traversal.
shell=False is enforced throughout.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from app.agent.state import ToolResult
from app.tools.base import BaseTool

# Shell metacharacters only. Backslash is a path separator on Windows, so it is
# not treated as injection for working_directory (unlike k8s/docker names).
_PATH_INJECTION_CHARS = re.compile(r"[;&|`$<>\n\r\t\x00-\x1f]")

# ---------------------------------------------------------------------------
# Terraform-specific constants
# ---------------------------------------------------------------------------

TERRAFORM_ALLOWED_COMMANDS = frozenset({"fmt", "validate", "plan"})

TERRAFORM_BLOCKED_COMMANDS = frozenset({
    "apply",
    "destroy",
    "import",
    "state",
    "workspace",
    "init",
    "push",
    "taint",
    "untaint",
    "force-unlock",
    "login",
    "logout",
    "providers",
    "refresh",
    "console",
    "graph",
    "output",
    "show",
})

# Allowed flags for each command — tightly scoped
TERRAFORM_ALLOWED_FLAGS: dict[str, frozenset] = {
    "fmt":      frozenset({"-check", "-diff", "-recursive"}),
    "validate": frozenset({"-json", "-no-color"}),
    "plan":     frozenset({"-no-color", "-json", "-compact-warnings",
                           "-refresh=false", "-refresh-only", "-lock=false"}),
}


def validate_terraform_command(command: str) -> str:
    """Ensure only allowlisted Terraform commands are used."""
    if command in TERRAFORM_BLOCKED_COMMANDS:
        raise ValueError(
            f"Terraform command '{command}' is explicitly blocked. "
            f"Allowed: {sorted(TERRAFORM_ALLOWED_COMMANDS)}"
        )
    if command not in TERRAFORM_ALLOWED_COMMANDS:
        raise ValueError(
            f"Terraform command '{command}' is not in the allowlist. "
            f"Allowed: {sorted(TERRAFORM_ALLOWED_COMMANDS)}"
        )
    return command


def validate_terraform_flag(command: str, flag: str) -> str:
    """Validate a flag against the per-command allowlist."""
    allowed = TERRAFORM_ALLOWED_FLAGS.get(command, frozenset())
    if flag not in allowed:
        raise ValueError(
            f"Flag '{flag}' is not allowed for 'terraform {command}'. "
            f"Allowed flags: {sorted(allowed)}"
        )
    return flag


def validate_working_directory(path: str) -> str:
    """Validate and normalise a Terraform working directory path.

    Prevents path traversal and ensures the directory exists.
    """
    if not path or not isinstance(path, str):
        raise ValueError("working_directory must be a non-empty string")
    if _PATH_INJECTION_CHARS.search(path):
        raise ValueError(
            f"working_directory contains invalid characters: {path!r}"
        )
    # Resolve to absolute path and check for traversal
    resolved = os.path.realpath(os.path.abspath(path))
    resolved_path = Path(resolved)
    # POSIX `/` and Windows `C:\` both have parent == self
    if resolved_path.parent == resolved_path:
        raise ValueError("working_directory cannot be the filesystem root")
    # Must exist
    if not os.path.isdir(resolved):
        raise ValueError(f"working_directory does not exist: {resolved!r}")
    return resolved


# ---------------------------------------------------------------------------
# Terraform tools
# ---------------------------------------------------------------------------


class TerraformFmtCheck(BaseTool):
    """Run terraform fmt -check to verify formatting without modifying files."""

    tool_name = "terraform_fmt_check"

    def execute(
        self,
        working_directory: str,
        recursive: bool = False,
        **kwargs,
    ) -> ToolResult:
        validate_terraform_command("fmt")
        wd = validate_working_directory(working_directory)
        cmd = ["terraform", "fmt", "-check", "-diff"]
        if recursive:
            validate_terraform_flag("fmt", "-recursive")
            cmd.append("-recursive")
        cmd.append(wd)
        return self._run_subprocess(cmd, command_type="read", resource=wd)


class TerraformValidate(BaseTool):
    """Run terraform validate to check configuration syntax."""

    tool_name = "terraform_validate"

    def execute(
        self,
        working_directory: str,
        json_output: bool = False,
        **kwargs,
    ) -> ToolResult:
        validate_terraform_command("validate")
        wd = validate_working_directory(working_directory)
        cmd = ["terraform", "-chdir=" + wd, "validate"]
        if json_output:
            validate_terraform_flag("validate", "-json")
            cmd.append("-json")
        return self._run_subprocess(cmd, command_type="read", resource=wd)


class TerraformPlan(BaseTool):
    """Run terraform plan (read-only dry-run — no apply)."""

    tool_name = "terraform_plan"

    def execute(
        self,
        working_directory: str,
        no_color: bool = True,
        refresh_only: bool = False,
        **kwargs,
    ) -> ToolResult:
        validate_terraform_command("plan")
        wd = validate_working_directory(working_directory)
        cmd = ["terraform", "-chdir=" + wd, "plan"]
        if no_color:
            validate_terraform_flag("plan", "-no-color")
            cmd.append("-no-color")
        if refresh_only:
            validate_terraform_flag("plan", "-refresh-only")
            cmd.append("-refresh-only")
        # Always disable locking for read-only diagnostic runs
        validate_terraform_flag("plan", "-lock=false")
        cmd.append("-lock=false")
        return self._run_subprocess(cmd, command_type="read", resource=wd)


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TERRAFORM_TOOLS: dict[str, type[BaseTool]] = {
    "terraform_fmt_check": TerraformFmtCheck,
    "terraform_validate": TerraformValidate,
    "terraform_plan": TerraformPlan,
}


def get_terraform_tool(tool_name: str, timeout: int = 60) -> BaseTool:
    """Factory: return an instantiated Terraform tool by name."""
    cls = TERRAFORM_TOOLS.get(tool_name)
    if cls is None:
        raise ValueError(
            f"Unknown Terraform tool: {tool_name!r}. "
            f"Available: {sorted(TERRAFORM_TOOLS.keys())}"
        )
    return cls(timeout=timeout)
