"""Unit tests for read-only Terraform tools."""

from __future__ import annotations

import os
import subprocess
import tempfile
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_proc(stdout="", stderr="", returncode=0):
    m = MagicMock(spec=subprocess.CompletedProcess)
    m.stdout = stdout
    m.stderr = stderr
    m.returncode = returncode
    return m


@pytest.fixture
def tf_dir():
    """Create a temporary directory simulating a Terraform workspace."""
    with tempfile.TemporaryDirectory() as tmp:
        # Write a minimal main.tf so the directory looks like a Terraform workspace
        with open(os.path.join(tmp, "main.tf"), "w") as f:
            f.write('variable "env" { default = "dev" }\n')
        yield tmp


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidateTerraformCommand:
    def test_fmt_allowed(self):
        from app.tools.terraform.tools import validate_terraform_command
        assert validate_terraform_command("fmt") == "fmt"

    def test_validate_allowed(self):
        from app.tools.terraform.tools import validate_terraform_command
        assert validate_terraform_command("validate") == "validate"

    def test_plan_allowed(self):
        from app.tools.terraform.tools import validate_terraform_command
        assert validate_terraform_command("plan") == "plan"

    def test_apply_blocked(self):
        from app.tools.terraform.tools import validate_terraform_command
        with pytest.raises(ValueError, match="explicitly blocked"):
            validate_terraform_command("apply")

    def test_destroy_blocked(self):
        from app.tools.terraform.tools import validate_terraform_command
        with pytest.raises(ValueError, match="explicitly blocked"):
            validate_terraform_command("destroy")

    def test_import_blocked(self):
        from app.tools.terraform.tools import validate_terraform_command
        with pytest.raises(ValueError, match="explicitly blocked"):
            validate_terraform_command("import")

    def test_state_blocked(self):
        from app.tools.terraform.tools import validate_terraform_command
        with pytest.raises(ValueError, match="explicitly blocked"):
            validate_terraform_command("state")

    def test_unknown_not_allowed(self):
        from app.tools.terraform.tools import validate_terraform_command, TERRAFORM_BLOCKED_COMMANDS, TERRAFORM_ALLOWED_COMMANDS
        # "taint" is in BLOCKED list
        with pytest.raises(ValueError):
            validate_terraform_command("taint")
        # Find a command that is neither blocked nor allowed
        unknown_cmd = "terraform-custom-subcommand"
        assert unknown_cmd not in TERRAFORM_BLOCKED_COMMANDS
        assert unknown_cmd not in TERRAFORM_ALLOWED_COMMANDS
        with pytest.raises(ValueError, match="not in the allowlist"):
            validate_terraform_command(unknown_cmd)


class TestValidateTerraformFlag:
    def test_check_flag_for_fmt(self):
        from app.tools.terraform.tools import validate_terraform_flag
        assert validate_terraform_flag("fmt", "-check") == "-check"

    def test_json_flag_for_validate(self):
        from app.tools.terraform.tools import validate_terraform_flag
        assert validate_terraform_flag("validate", "-json") == "-json"

    def test_no_color_for_plan(self):
        from app.tools.terraform.tools import validate_terraform_flag
        assert validate_terraform_flag("plan", "-no-color") == "-no-color"

    def test_disallowed_flag_raises(self):
        from app.tools.terraform.tools import validate_terraform_flag
        with pytest.raises(ValueError):
            validate_terraform_flag("plan", "-destroy")

    def test_out_flag_not_allowed_for_plan(self):
        from app.tools.terraform.tools import validate_terraform_flag
        with pytest.raises(ValueError):
            validate_terraform_flag("plan", "-out=tfplan")


class TestValidateWorkingDirectory:
    def test_valid_directory(self, tf_dir):
        from app.tools.terraform.tools import validate_working_directory
        result = validate_working_directory(tf_dir)
        assert os.path.isdir(result)

    def test_nonexistent_directory_raises(self):
        from app.tools.terraform.tools import validate_working_directory
        with pytest.raises(ValueError, match="does not exist"):
            validate_working_directory("/nonexistent/path/xyz")

    def test_root_directory_raises(self):
        from app.tools.terraform.tools import validate_working_directory
        with pytest.raises(ValueError):
            validate_working_directory("/")

    @pytest.mark.skipif(os.name != "nt", reason="Windows drive-root check")
    def test_windows_drive_root_raises(self):
        from app.tools.terraform.tools import validate_working_directory
        with pytest.raises(ValueError, match="filesystem root"):
            validate_working_directory("C:\\")

    def test_injection_in_path_raises(self):
        from app.tools.terraform.tools import validate_working_directory
        with pytest.raises(ValueError):
            validate_working_directory("/tmp; rm -rf /")

    def test_empty_path_raises(self):
        from app.tools.terraform.tools import validate_working_directory
        with pytest.raises(ValueError):
            validate_working_directory("")


# ---------------------------------------------------------------------------
# TerraformFmtCheck
# ---------------------------------------------------------------------------

class TestTerraformFmtCheck:
    @patch("subprocess.run")
    def test_success_well_formatted(self, mock_run, tf_dir):
        mock_run.return_value = _make_proc(stdout="", returncode=0)
        from app.tools.terraform.tools import TerraformFmtCheck
        result = TerraformFmtCheck().execute(working_directory=tf_dir)
        assert result.status == "success"
        assert result.exit_code == 0

    @patch("subprocess.run")
    def test_formatting_issues_detected(self, mock_run, tf_dir):
        mock_run.return_value = _make_proc(
            stdout="main.tf\n", returncode=1
        )
        from app.tools.terraform.tools import TerraformFmtCheck
        result = TerraformFmtCheck().execute(working_directory=tf_dir)
        assert result.status == "error"
        assert result.exit_code == 1

    @patch("subprocess.run")
    def test_terraform_not_found(self, mock_run, tf_dir):
        mock_run.side_effect = FileNotFoundError("terraform not found")
        from app.tools.terraform.tools import TerraformFmtCheck
        result = TerraformFmtCheck().execute(working_directory=tf_dir)
        assert result.status == "not_found"

    @patch("subprocess.run")
    def test_timeout(self, mock_run, tf_dir):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["terraform"], timeout=60)
        from app.tools.terraform.tools import TerraformFmtCheck
        result = TerraformFmtCheck().execute(working_directory=tf_dir)
        assert result.status == "timeout"

    def test_invalid_directory_raises(self):
        from app.tools.terraform.tools import TerraformFmtCheck
        with pytest.raises(ValueError):
            TerraformFmtCheck().execute(working_directory="/nonexistent/xyz")

    def test_path_traversal_raises(self):
        from app.tools.terraform.tools import TerraformFmtCheck
        with pytest.raises(ValueError):
            TerraformFmtCheck().execute(working_directory="/tmp; rm -rf /")

    @patch("subprocess.run")
    def test_check_flag_in_command(self, mock_run, tf_dir):
        mock_run.return_value = _make_proc()
        from app.tools.terraform.tools import TerraformFmtCheck
        TerraformFmtCheck().execute(working_directory=tf_dir)
        cmd = mock_run.call_args[0][0]
        assert "-check" in cmd
        assert "apply" not in cmd
        assert "destroy" not in cmd


# ---------------------------------------------------------------------------
# TerraformValidate
# ---------------------------------------------------------------------------

class TestTerraformValidate:
    @patch("subprocess.run")
    def test_success(self, mock_run, tf_dir):
        mock_run.return_value = _make_proc(
            stdout="Success! The configuration is valid.\n", returncode=0
        )
        from app.tools.terraform.tools import TerraformValidate
        result = TerraformValidate().execute(working_directory=tf_dir)
        assert result.status == "success"

    @patch("subprocess.run")
    def test_validation_failure(self, mock_run, tf_dir):
        mock_run.return_value = _make_proc(
            stderr="Error: Unsupported argument\n", returncode=1
        )
        from app.tools.terraform.tools import TerraformValidate
        result = TerraformValidate().execute(working_directory=tf_dir)
        assert result.status == "error"

    @patch("subprocess.run")
    def test_json_output(self, mock_run, tf_dir):
        mock_run.return_value = _make_proc(stdout='{"valid": true}', returncode=0)
        from app.tools.terraform.tools import TerraformValidate
        result = TerraformValidate().execute(working_directory=tf_dir, json_output=True)
        cmd = mock_run.call_args[0][0]
        assert "-json" in cmd

    def test_path_traversal_raises(self):
        from app.tools.terraform.tools import TerraformValidate
        # Path with injection characters must be rejected
        with pytest.raises(ValueError):
            TerraformValidate().execute(working_directory="/tmp; rm -rf /")


# ---------------------------------------------------------------------------
# TerraformPlan
# ---------------------------------------------------------------------------

class TestTerraformPlan:
    @patch("subprocess.run")
    def test_success(self, mock_run, tf_dir):
        mock_run.return_value = _make_proc(
            stdout="No changes. Your infrastructure matches the configuration.\n",
            returncode=0,
        )
        from app.tools.terraform.tools import TerraformPlan
        result = TerraformPlan().execute(working_directory=tf_dir)
        assert result.status == "success"

    @patch("subprocess.run")
    def test_lock_false_always_set(self, mock_run, tf_dir):
        mock_run.return_value = _make_proc()
        from app.tools.terraform.tools import TerraformPlan
        TerraformPlan().execute(working_directory=tf_dir)
        cmd = mock_run.call_args[0][0]
        assert "-lock=false" in cmd

    @patch("subprocess.run")
    def test_no_apply_in_command(self, mock_run, tf_dir):
        mock_run.return_value = _make_proc()
        from app.tools.terraform.tools import TerraformPlan
        TerraformPlan().execute(working_directory=tf_dir)
        cmd = mock_run.call_args[0][0]
        assert "apply" not in cmd
        assert "destroy" not in cmd

    @patch("subprocess.run")
    def test_auth_error(self, mock_run, tf_dir):
        mock_run.return_value = _make_proc(
            stderr="Error: Failed to refresh state: ... credential not found",
            returncode=1,
        )
        from app.tools.terraform.tools import TerraformPlan
        result = TerraformPlan().execute(working_directory=tf_dir)
        assert result.status == "error"

    def test_invalid_directory_raises(self):
        from app.tools.terraform.tools import TerraformPlan
        with pytest.raises(ValueError):
            TerraformPlan().execute(working_directory="/nonexistent/tf")


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

class TestTerraformToolRegistry:
    def test_all_3_tools_registered(self):
        from app.tools.terraform.tools import TERRAFORM_TOOLS
        assert set(TERRAFORM_TOOLS.keys()) == {
            "terraform_fmt_check", "terraform_validate", "terraform_plan"
        }

    def test_get_tool_by_name(self):
        from app.tools.terraform.tools import get_terraform_tool
        assert get_terraform_tool("terraform_plan").tool_name == "terraform_plan"

    def test_unknown_tool_raises(self):
        from app.tools.terraform.tools import get_terraform_tool
        with pytest.raises(ValueError, match="Unknown Terraform tool"):
            get_terraform_tool("terraform_apply")


# ---------------------------------------------------------------------------
# Security: destructive Terraform operations blocked
# ---------------------------------------------------------------------------

class TestTerraformDestructiveBlocked:
    BLOCKED = ["apply", "destroy", "import", "state", "taint", "force-unlock"]

    @pytest.mark.parametrize("cmd", BLOCKED)
    def test_blocked_command_raises(self, cmd):
        from app.tools.terraform.tools import validate_terraform_command
        with pytest.raises(ValueError):
            validate_terraform_command(cmd)

    def test_plan_out_flag_not_allowed(self):
        """Ensure -out=<file> cannot be used to persist a plan for apply."""
        from app.tools.terraform.tools import validate_terraform_flag
        with pytest.raises(ValueError):
            validate_terraform_flag("plan", "-out=tfplan")

    def test_apply_cannot_be_constructed_from_plan_output(self):
        """terraform apply cannot be constructed — apply is blocked."""
        from app.tools.terraform.tools import validate_terraform_command
        with pytest.raises(ValueError, match="explicitly blocked"):
            validate_terraform_command("apply")
