"""Unit tests for read-only Docker tools."""

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

class TestValidateDockerCommand:
    def test_images_allowed(self):
        from app.tools.docker.tools import validate_docker_command
        assert validate_docker_command("images") == "images"

    def test_ps_allowed(self):
        from app.tools.docker.tools import validate_docker_command
        assert validate_docker_command("ps") == "ps"

    def test_inspect_allowed(self):
        from app.tools.docker.tools import validate_docker_command
        assert validate_docker_command("inspect") == "inspect"

    def test_rm_blocked(self):
        from app.tools.docker.tools import validate_docker_command
        with pytest.raises(ValueError, match="explicitly blocked"):
            validate_docker_command("rm")

    def test_rmi_blocked(self):
        from app.tools.docker.tools import validate_docker_command
        with pytest.raises(ValueError, match="explicitly blocked"):
            validate_docker_command("rmi")

    def test_kill_blocked(self):
        from app.tools.docker.tools import validate_docker_command
        with pytest.raises(ValueError, match="explicitly blocked"):
            validate_docker_command("kill")

    def test_system_blocked(self):
        from app.tools.docker.tools import validate_docker_command
        with pytest.raises(ValueError, match="explicitly blocked"):
            validate_docker_command("system")

    def test_exec_blocked(self):
        from app.tools.docker.tools import validate_docker_command
        with pytest.raises(ValueError, match="explicitly blocked"):
            validate_docker_command("exec")

    def test_run_blocked(self):
        from app.tools.docker.tools import validate_docker_command
        with pytest.raises(ValueError, match="explicitly blocked"):
            validate_docker_command("run")

    def test_unknown_not_allowed(self):
        from app.tools.docker.tools import validate_docker_command
        with pytest.raises(ValueError, match="not in the allowlist"):
            validate_docker_command("arbitrary")


class TestValidateDockerImage:
    def test_valid_image(self):
        from app.tools.docker.tools import validate_docker_image
        assert validate_docker_image(
            "us-central1-docker.pkg.dev/gcp-dev-july-2026/"
            "employment-management/employment-management:1.0.0"
        )

    def test_simple_image(self):
        from app.tools.docker.tools import validate_docker_image
        assert validate_docker_image("nginx:latest") == "nginx:latest"

    def test_injection_raises(self):
        from app.tools.docker.tools import validate_docker_image
        with pytest.raises(ValueError):
            validate_docker_image("nginx; rm -rf /")

    def test_empty_raises(self):
        from app.tools.docker.tools import validate_docker_image
        with pytest.raises(ValueError):
            validate_docker_image("")


class TestValidateDockerContainer:
    def test_valid_container_name(self):
        from app.tools.docker.tools import validate_docker_container
        assert validate_docker_container("my-container-123") == "my-container-123"

    def test_injection_raises(self):
        from app.tools.docker.tools import validate_docker_container
        with pytest.raises(ValueError):
            validate_docker_container("container|id")

    def test_empty_raises(self):
        from app.tools.docker.tools import validate_docker_container
        with pytest.raises(ValueError):
            validate_docker_container("")


# ---------------------------------------------------------------------------
# DockerImages
# ---------------------------------------------------------------------------

class TestDockerImages:
    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _make_proc(
            stdout="REPOSITORY  TAG  IMAGE ID  CREATED  SIZE\n"
                   "nginx       latest  abc123  2 days ago  142MB"
        )
        from app.tools.docker.tools import DockerImages
        result = DockerImages().execute()
        assert result.status == "success"
        assert "nginx" in result.stdout

    @patch("subprocess.run")
    def test_with_repository_filter(self, mock_run):
        mock_run.return_value = _make_proc(stdout="nginx info")
        from app.tools.docker.tools import DockerImages
        DockerImages().execute(repository="nginx:latest")
        cmd = mock_run.call_args[0][0]
        assert "nginx:latest" in cmd

    @patch("subprocess.run")
    def test_no_shell_true(self, mock_run):
        mock_run.return_value = _make_proc()
        from app.tools.docker.tools import DockerImages
        DockerImages().execute()
        assert mock_run.call_args[1].get("shell") is False or \
               "shell" not in mock_run.call_args[1]

    @patch("subprocess.run")
    def test_docker_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("docker not found")
        from app.tools.docker.tools import DockerImages
        result = DockerImages().execute()
        assert result.status == "not_found"

    @patch("subprocess.run")
    def test_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["docker"], timeout=30)
        from app.tools.docker.tools import DockerImages
        result = DockerImages().execute()
        assert result.status == "timeout"

    @patch("subprocess.run")
    def test_permission_error(self, mock_run):
        mock_run.return_value = _make_proc(
            stderr="Got permission denied while trying to connect to the Docker daemon socket",
            returncode=1,
        )
        from app.tools.docker.tools import DockerImages
        result = DockerImages().execute()
        assert result.status == "error"
        assert result.exit_code == 1

    def test_injection_in_repository_raises(self):
        from app.tools.docker.tools import DockerImages
        with pytest.raises(ValueError):
            DockerImages().execute(repository="nginx; rm -rf /")


# ---------------------------------------------------------------------------
# DockerPs
# ---------------------------------------------------------------------------

class TestDockerPs:
    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _make_proc(
            stdout="CONTAINER ID  IMAGE  COMMAND  STATUS  NAMES\n"
                   "abc123  nginx  nginx  Up 2h  web"
        )
        from app.tools.docker.tools import DockerPs
        result = DockerPs().execute()
        assert result.status == "success"

    @patch("subprocess.run")
    def test_all_containers_flag(self, mock_run):
        mock_run.return_value = _make_proc()
        from app.tools.docker.tools import DockerPs
        DockerPs().execute(all_containers=True)
        cmd = mock_run.call_args[0][0]
        assert "--all" in cmd

    @patch("subprocess.run")
    def test_daemon_not_running(self, mock_run):
        mock_run.return_value = _make_proc(
            stderr="Cannot connect to the Docker daemon at unix:///var/run/docker.sock",
            returncode=1,
        )
        from app.tools.docker.tools import DockerPs
        result = DockerPs().execute()
        assert result.status == "error"


# ---------------------------------------------------------------------------
# DockerInspect
# ---------------------------------------------------------------------------

class TestDockerInspect:
    @patch("subprocess.run")
    def test_inspect_container_success(self, mock_run):
        mock_run.return_value = _make_proc(stdout='[{"Id": "abc123", "State": {}}]')
        from app.tools.docker.tools import DockerInspect
        result = DockerInspect().execute(target="my-container", inspect_type="container")
        assert result.status == "success"
        assert result.resource == "my-container"

    @patch("subprocess.run")
    def test_inspect_image_success(self, mock_run):
        mock_run.return_value = _make_proc(stdout='[{"Id": "sha256:abc"}]')
        from app.tools.docker.tools import DockerInspect
        result = DockerInspect().execute(target="nginx:latest", inspect_type="image")
        assert result.status == "success"

    def test_invalid_inspect_type_raises(self):
        from app.tools.docker.tools import DockerInspect
        with pytest.raises(ValueError, match="inspect_type"):
            DockerInspect().execute(target="something", inspect_type="network")

    def test_injection_in_target_raises(self):
        from app.tools.docker.tools import DockerInspect
        with pytest.raises(ValueError):
            DockerInspect().execute(target="container; id", inspect_type="container")

    @patch("subprocess.run")
    def test_container_not_found(self, mock_run):
        mock_run.return_value = _make_proc(
            stderr="Error: No such container: missing-container",
            returncode=1,
        )
        from app.tools.docker.tools import DockerInspect
        result = DockerInspect().execute(target="missing-container", inspect_type="container")
        assert result.status == "error"


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

class TestDockerToolRegistry:
    def test_all_3_tools_registered(self):
        from app.tools.docker.tools import DOCKER_TOOLS
        assert set(DOCKER_TOOLS.keys()) == {"docker_images", "docker_ps", "docker_inspect"}

    def test_get_tool_by_name(self):
        from app.tools.docker.tools import get_docker_tool
        assert get_docker_tool("docker_images").tool_name == "docker_images"

    def test_unknown_tool_raises(self):
        from app.tools.docker.tools import get_docker_tool
        with pytest.raises(ValueError, match="Unknown Docker tool"):
            get_docker_tool("docker_rm_all")


# ---------------------------------------------------------------------------
# Security: destructive Docker commands blocked
# ---------------------------------------------------------------------------

class TestDockerDestructiveBlocked:
    BLOCKED = ["rm", "rmi", "kill", "stop", "system", "exec", "run",
               "build", "push", "create", "restart"]

    @pytest.mark.parametrize("cmd", BLOCKED)
    def test_blocked_command_raises(self, cmd):
        from app.tools.docker.tools import validate_docker_command
        with pytest.raises(ValueError):
            validate_docker_command(cmd)

    @pytest.mark.parametrize("injection", [
        "container; rm -rf /",
        "container | cat /etc/shadow",
        "container`id`",
        "container$(whoami)",
        "container\nrm",
        "../../../etc/passwd",
    ])
    def test_container_injection_rejected(self, injection):
        from app.tools.docker.tools import DockerInspect
        with pytest.raises(ValueError):
            DockerInspect().execute(target=injection, inspect_type="container")
