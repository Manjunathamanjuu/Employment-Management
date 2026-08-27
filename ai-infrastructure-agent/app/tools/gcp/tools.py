"""Read-only GCP diagnostic tools.

Allowed read-only operations:
  - gcloud config get-value project
  - gcloud container clusters describe <cluster> --region=<region>
  - gcloud compute instances describe <instance> --zone=<zone>

Destructive operations are never exposed.
Authentication errors and permission errors are returned as structured results.
shell=False is enforced throughout.
"""

from __future__ import annotations

import re
from typing import Optional

from app.agent.state import ToolResult
from app.config import settings
from app.tools.base import BaseTool, _DANGEROUS_CHARS

# ---------------------------------------------------------------------------
# GCP-specific validation
# ---------------------------------------------------------------------------

# GCP resource names: lowercase alphanumeric and hyphens
_GCP_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-]{0,62}[a-z0-9]$|^[a-z0-9]$")

# GCP project IDs
_GCP_PROJECT_PATTERN = re.compile(r"^[a-z][a-z0-9\-]{4,28}[a-z0-9]$")

# GCP zones/regions: e.g. us-central1, us-central1-a
_GCP_ZONE_PATTERN = re.compile(r"^[a-z]+-[a-z]+[0-9]+(-[a-z])?$")

# Allowed gcloud subcommand groups + actions
GCLOUD_ALLOWED_OPERATIONS = frozenset({
    ("config", "get-value"),
    ("container", "clusters", "describe"),
    ("compute", "instances", "describe"),
    ("compute", "instances", "list"),
    ("container", "clusters", "list"),
})

# Blocked gcloud operations — never expose these
GCLOUD_BLOCKED_OPERATIONS = frozenset({
    "delete", "create", "update", "patch", "set",
    "add", "remove", "attach", "detach", "deploy",
    "apply", "reset", "start", "stop", "restart",
    "ssh", "scp", "tunnel", "connect",
})


def validate_gcp_name(name: str, field: str = "resource") -> str:
    """Validate a GCP resource name."""
    if not name or not isinstance(name, str):
        raise ValueError(f"{field} must be a non-empty string")
    name = name.strip()
    if _DANGEROUS_CHARS.search(name):
        raise ValueError(f"{field} contains invalid characters: {name!r}")
    if not _GCP_NAME_PATTERN.match(name):
        raise ValueError(f"Invalid GCP {field}: {name!r}")
    return name


def validate_gcp_project(project_id: str) -> str:
    """Validate a GCP project ID."""
    if not project_id or not isinstance(project_id, str):
        raise ValueError("project_id must be a non-empty string")
    project_id = project_id.strip()
    if _DANGEROUS_CHARS.search(project_id):
        raise ValueError(f"project_id contains invalid characters: {project_id!r}")
    if not _GCP_PROJECT_PATTERN.match(project_id):
        raise ValueError(f"Invalid GCP project ID: {project_id!r}")
    return project_id


def validate_gcp_zone(zone: str) -> str:
    """Validate a GCP zone or region."""
    if not zone or not isinstance(zone, str):
        raise ValueError("zone/region must be a non-empty string")
    zone = zone.strip()
    if _DANGEROUS_CHARS.search(zone):
        raise ValueError(f"zone/region contains invalid characters: {zone!r}")
    if not _GCP_ZONE_PATTERN.match(zone):
        raise ValueError(f"Invalid GCP zone/region: {zone!r}")
    return zone


def validate_gcp_operation(operation_parts: list[str]) -> None:
    """Ensure the gcloud operation is in the allowlist."""
    key = tuple(operation_parts)
    for blocked in GCLOUD_BLOCKED_OPERATIONS:
        if blocked in operation_parts:
            raise ValueError(
                f"gcloud operation contains blocked verb '{blocked}'. "
                f"Only read-only operations are permitted."
            )
    if key not in GCLOUD_ALLOWED_OPERATIONS:
        raise ValueError(
            f"gcloud operation {key!r} is not in the allowlist. "
            f"Allowed: {sorted(str(op) for op in GCLOUD_ALLOWED_OPERATIONS)}"
        )


# ---------------------------------------------------------------------------
# GCP tools
# ---------------------------------------------------------------------------


class GCloudConfigGetProject(BaseTool):
    """Get the current GCP project from gcloud config."""

    tool_name = "gcloud_config_project"

    def execute(self, **kwargs) -> ToolResult:
        validate_gcp_operation(["config", "get-value"])
        cmd = ["gcloud", "config", "get-value", "project"]
        return self._run_subprocess(cmd, command_type="read")


class GCloudDescribeCluster(BaseTool):
    """Describe a GKE cluster."""

    tool_name = "gcloud_describe_cluster"

    def execute(
        self,
        cluster_name: Optional[str] = None,
        region: Optional[str] = None,
        project: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        validate_gcp_operation(["container", "clusters", "describe"])

        cluster = validate_gcp_name(
            cluster_name or settings.gke_cluster_name, "cluster_name"
        )
        reg = validate_gcp_zone(region or settings.gke_region)
        proj = validate_gcp_project(project or settings.gcp_project_id)

        cmd = [
            "gcloud", "container", "clusters", "describe", cluster,
            f"--region={reg}",
            f"--project={proj}",
            "--format=yaml",
        ]
        return self._run_subprocess(
            cmd, command_type="read", resource=cluster
        )


class GCloudListClusters(BaseTool):
    """List GKE clusters in a project."""

    tool_name = "gcloud_list_clusters"

    def execute(
        self,
        region: Optional[str] = None,
        project: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        validate_gcp_operation(["container", "clusters", "list"])

        reg = validate_gcp_zone(region or settings.gke_region)
        proj = validate_gcp_project(project or settings.gcp_project_id)

        cmd = [
            "gcloud", "container", "clusters", "list",
            f"--region={reg}",
            f"--project={proj}",
            "--format=table(name,location,status,currentNodeCount)",
        ]
        return self._run_subprocess(cmd, command_type="read")


class GCloudDescribeInstance(BaseTool):
    """Describe a GCP Compute Engine instance."""

    tool_name = "gcloud_describe_instance"

    def execute(
        self,
        instance_name: str,
        zone: str,
        project: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        validate_gcp_operation(["compute", "instances", "describe"])

        name = validate_gcp_name(instance_name, "instance_name")
        z = validate_gcp_zone(zone)
        proj = validate_gcp_project(project or settings.gcp_project_id)

        cmd = [
            "gcloud", "compute", "instances", "describe", name,
            f"--zone={z}",
            f"--project={proj}",
            "--format=yaml",
        ]
        return self._run_subprocess(
            cmd, command_type="read", resource=name
        )


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

GCP_TOOLS: dict[str, type[BaseTool]] = {
    "gcloud_config_project": GCloudConfigGetProject,
    "gcloud_describe_cluster": GCloudDescribeCluster,
    "gcloud_list_clusters": GCloudListClusters,
    "gcloud_describe_instance": GCloudDescribeInstance,
}


def get_gcp_tool(tool_name: str, timeout: int = 30) -> BaseTool:
    """Factory: return an instantiated GCP tool by name."""
    cls = GCP_TOOLS.get(tool_name)
    if cls is None:
        raise ValueError(
            f"Unknown GCP tool: {tool_name!r}. "
            f"Available: {sorted(GCP_TOOLS.keys())}"
        )
    return cls(timeout=timeout)
