"""Unit tests for read-only GCP tools."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_proc(stdout="", stderr="", returncode=0):
    m = MagicMock(spec=subprocess.CompletedProcess)
    m.stdout = stdout
    m.stderr = stderr
    m.returncode = returncode
    return m


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidateGcpName:
    def test_valid_name(self):
        from app.tools.gcp.tools import validate_gcp_name
        assert validate_gcp_name("employment-management-gke") == "employment-management-gke"

    def test_injection_raises(self):
        from app.tools.gcp.tools import validate_gcp_name
        with pytest.raises(ValueError):
            validate_gcp_name("cluster; rm -rf /")

    def test_empty_raises(self):
        from app.tools.gcp.tools import validate_gcp_name
        with pytest.raises(ValueError):
            validate_gcp_name("")


class TestValidateGcpProject:
    def test_valid_project(self):
        from app.tools.gcp.tools import validate_gcp_project
        assert validate_gcp_project("gcp-dev-july-2026") == "gcp-dev-july-2026"

    def test_injection_raises(self):
        from app.tools.gcp.tools import validate_gcp_project
        with pytest.raises(ValueError):
            validate_gcp_project("project|id")

    def test_empty_raises(self):
        from app.tools.gcp.tools import validate_gcp_project
        with pytest.raises(ValueError):
            validate_gcp_project("")


class TestValidateGcpZone:
    def test_valid_region(self):
        from app.tools.gcp.tools import validate_gcp_zone
        assert validate_gcp_zone("us-central1") == "us-central1"

    def test_valid_zone(self):
        from app.tools.gcp.tools import validate_gcp_zone
        assert validate_gcp_zone("us-central1-a") == "us-central1-a"

    def test_injection_raises(self):
        from app.tools.gcp.tools import validate_gcp_zone
        with pytest.raises(ValueError):
            validate_gcp_zone("us-central1; id")

    def test_invalid_format_raises(self):
        from app.tools.gcp.tools import validate_gcp_zone
        with pytest.raises(ValueError):
            validate_gcp_zone("InvalidZone")


class TestValidateGcpOperation:
    def test_config_get_value_allowed(self):
        from app.tools.gcp.tools import validate_gcp_operation
        validate_gcp_operation(["config", "get-value"])  # no error

    def test_describe_cluster_allowed(self):
        from app.tools.gcp.tools import validate_gcp_operation
        validate_gcp_operation(["container", "clusters", "describe"])

    def test_describe_instance_allowed(self):
        from app.tools.gcp.tools import validate_gcp_operation
        validate_gcp_operation(["compute", "instances", "describe"])

    def test_delete_blocked(self):
        from app.tools.gcp.tools import validate_gcp_operation
        with pytest.raises(ValueError, match="blocked"):
            validate_gcp_operation(["compute", "instances", "delete"])

    def test_create_blocked(self):
        from app.tools.gcp.tools import validate_gcp_operation
        with pytest.raises(ValueError, match="blocked"):
            validate_gcp_operation(["container", "clusters", "create"])

    def test_ssh_blocked(self):
        from app.tools.gcp.tools import validate_gcp_operation
        with pytest.raises(ValueError, match="blocked"):
            validate_gcp_operation(["compute", "ssh", "my-instance"])

    def test_unknown_operation_blocked(self):
        from app.tools.gcp.tools import validate_gcp_operation
        with pytest.raises(ValueError):
            validate_gcp_operation(["billing", "accounts", "list"])


# ---------------------------------------------------------------------------
# GCloudConfigGetProject
# ---------------------------------------------------------------------------

class TestGCloudConfigGetProject:
    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _make_proc(stdout="gcp-dev-july-2026\n")
        from app.tools.gcp.tools import GCloudConfigGetProject
        result = GCloudConfigGetProject().execute()
        assert result.status == "success"
        assert "gcp-dev-july-2026" in result.stdout

    @patch("subprocess.run")
    def test_gcloud_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("gcloud not found")
        from app.tools.gcp.tools import GCloudConfigGetProject
        result = GCloudConfigGetProject().execute()
        assert result.status == "not_found"

    @patch("subprocess.run")
    def test_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["gcloud"], timeout=30)
        from app.tools.gcp.tools import GCloudConfigGetProject
        result = GCloudConfigGetProject().execute()
        assert result.status == "timeout"


# ---------------------------------------------------------------------------
# GCloudDescribeCluster
# ---------------------------------------------------------------------------

class TestGCloudDescribeCluster:
    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _make_proc(
            stdout="name: employment-management-gke\nstatus: RUNNING"
        )
        from app.tools.gcp.tools import GCloudDescribeCluster
        result = GCloudDescribeCluster().execute(
            cluster_name="employment-management-gke",
            region="us-central1",
            project="gcp-dev-july-2026",
        )
        assert result.status == "success"
        assert result.resource == "employment-management-gke"

    @patch("subprocess.run")
    def test_uses_defaults_from_config(self, mock_run):
        mock_run.return_value = _make_proc(stdout="name: employment-management-gke")
        from app.tools.gcp.tools import GCloudDescribeCluster
        GCloudDescribeCluster().execute()
        cmd = mock_run.call_args[0][0]
        assert "employment-management-gke" in cmd
        assert "us-central1" in " ".join(cmd)

    @patch("subprocess.run")
    def test_auth_error(self, mock_run):
        mock_run.return_value = _make_proc(
            stderr="ERROR: (gcloud.container.clusters.describe) "
                   "There was a problem refreshing your current auth tokens",
            returncode=1,
        )
        from app.tools.gcp.tools import GCloudDescribeCluster
        result = GCloudDescribeCluster().execute()
        assert result.status == "error"
        assert result.exit_code == 1

    @patch("subprocess.run")
    def test_permission_denied(self, mock_run):
        mock_run.return_value = _make_proc(
            stderr="ERROR: (gcloud.container.clusters.describe) "
                   "PERMISSION_DENIED: Request had insufficient authentication scopes",
            returncode=1,
        )
        from app.tools.gcp.tools import GCloudDescribeCluster
        result = GCloudDescribeCluster().execute()
        assert result.status == "error"

    def test_injection_in_cluster_name_raises(self):
        from app.tools.gcp.tools import GCloudDescribeCluster
        with pytest.raises(ValueError):
            GCloudDescribeCluster().execute(
                cluster_name="cluster; gcloud projects list",
                region="us-central1",
            )

    def test_injection_in_region_raises(self):
        from app.tools.gcp.tools import GCloudDescribeCluster
        with pytest.raises(ValueError):
            GCloudDescribeCluster().execute(
                cluster_name="employment-management-gke",
                region="us-central1; rm -rf /",
            )

    def test_injection_in_project_raises(self):
        from app.tools.gcp.tools import GCloudDescribeCluster
        with pytest.raises(ValueError):
            GCloudDescribeCluster().execute(
                cluster_name="employment-management-gke",
                region="us-central1",
                project="project`id`",
            )


# ---------------------------------------------------------------------------
# GCloudDescribeInstance
# ---------------------------------------------------------------------------

class TestGCloudDescribeInstance:
    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _make_proc(stdout="name: my-node\nstatus: RUNNING")
        from app.tools.gcp.tools import GCloudDescribeInstance
        result = GCloudDescribeInstance().execute(
            instance_name="my-node",
            zone="us-central1-a",
            project="gcp-dev-july-2026",
        )
        assert result.status == "success"
        assert result.resource == "my-node"

    def test_injection_in_instance_name_raises(self):
        from app.tools.gcp.tools import GCloudDescribeInstance
        with pytest.raises(ValueError):
            GCloudDescribeInstance().execute(
                instance_name="instance; id",
                zone="us-central1-a",
            )

    def test_injection_in_zone_raises(self):
        from app.tools.gcp.tools import GCloudDescribeInstance
        with pytest.raises(ValueError):
            GCloudDescribeInstance().execute(
                instance_name="my-node",
                zone="us-central1-a; id",
            )


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

class TestGcpToolRegistry:
    def test_all_4_tools_registered(self):
        from app.tools.gcp.tools import GCP_TOOLS
        assert set(GCP_TOOLS.keys()) == {
            "gcloud_config_project", "gcloud_describe_cluster",
            "gcloud_list_clusters", "gcloud_describe_instance",
        }

    def test_get_tool_by_name(self):
        from app.tools.gcp.tools import get_gcp_tool
        assert get_gcp_tool("gcloud_describe_cluster").tool_name == "gcloud_describe_cluster"

    def test_unknown_tool_raises(self):
        from app.tools.gcp.tools import get_gcp_tool
        with pytest.raises(ValueError, match="Unknown GCP tool"):
            get_gcp_tool("gcloud_delete_cluster")
