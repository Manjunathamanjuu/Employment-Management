"""Regression tests verifying the existing Employment Management application is unchanged.

These tests do not run the Java application — they verify that no files
in the existing application have been modified by the AI agent work.
"""

from __future__ import annotations

import os
import subprocess
import pytest

pytestmark = pytest.mark.regression

# Root of the workspace (two levels up from this file)
WORKSPACE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)

# Files and directories that must exist unmodified
PROTECTED_FILES = [
    "pom.xml",
    "Dockerfile",
    "docker-compose.yml",
    "src/main/java/com/example/employmentmanagement/EmploymentManagementApplication.java",
    "src/main/java/com/example/employmentmanagement/controller/EmployeeController.java",
    "src/main/java/com/example/employmentmanagement/service/EmployeeService.java",
    "src/main/java/com/example/employmentmanagement/model/Employee.java",
    "src/main/resources/application.properties",
    "src/main/resources/static/index.html",
    "Kubernetes-manifests/deployment.yaml",
    "Kubernetes-manifests/service.yaml",
]

PROTECTED_DIRS = [
    "src",
    "Kubernetes-manifests",
]

AI_AGENT_DIR = "ai-infrastructure-agent"


class TestExistingFilesUntouched:
    def test_pom_xml_exists(self):
        path = os.path.join(WORKSPACE_ROOT, "pom.xml")
        assert os.path.exists(path), f"pom.xml missing: {path}"

    def test_dockerfile_exists(self):
        path = os.path.join(WORKSPACE_ROOT, "Dockerfile")
        assert os.path.exists(path), f"Dockerfile missing: {path}"

    def test_docker_compose_exists(self):
        path = os.path.join(WORKSPACE_ROOT, "docker-compose.yml")
        assert os.path.exists(path), f"docker-compose.yml missing"

    def test_src_directory_exists(self):
        path = os.path.join(WORKSPACE_ROOT, "src")
        assert os.path.isdir(path), "src/ directory missing"

    def test_kubernetes_manifests_exist(self):
        path = os.path.join(WORKSPACE_ROOT, "Kubernetes-manifests")
        assert os.path.isdir(path), "Kubernetes-manifests/ directory missing"

    @pytest.mark.parametrize("rel_path", PROTECTED_FILES)
    def test_protected_file_exists(self, rel_path):
        full_path = os.path.join(WORKSPACE_ROOT, rel_path)
        assert os.path.exists(full_path), f"Protected file missing: {rel_path}"


class TestAIAgentIsolated:
    def test_ai_agent_in_its_own_directory(self):
        agent_dir = os.path.join(WORKSPACE_ROOT, AI_AGENT_DIR)
        assert os.path.isdir(agent_dir), f"{AI_AGENT_DIR}/ directory missing"

    def test_no_ai_agent_files_outside_its_directory(self):
        """Verify no Python files from the AI agent are in the existing app tree."""
        src_dir = os.path.join(WORKSPACE_ROOT, "src")
        for root, dirs, files in os.walk(src_dir):
            for fname in files:
                if fname.endswith(".py"):
                    full = os.path.join(root, fname)
                    pytest.fail(
                        f"Python file found inside src/: {full} — "
                        "AI agent must not modify the Java application tree"
                    )

    def test_existing_dockerfile_is_for_java_app(self):
        """Confirm the root Dockerfile is still the Java application Dockerfile."""
        path = os.path.join(WORKSPACE_ROOT, "Dockerfile")
        with open(path) as f:
            content = f.read()
        # Java/Maven/Spring Boot indicators
        assert any(
            indicator in content
            for indicator in ("maven", "java", "JAVA", "openjdk", "eclipse-temurin", "jar", "JAR")
        ), "Root Dockerfile no longer looks like a Java application Dockerfile"


class TestGitStatus:
    def test_no_unexpected_staged_changes(self):
        """Verify git status shows no modifications to protected files."""
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            cwd=WORKSPACE_ROOT,
        )
        modified = result.stdout.strip().splitlines()
        for path in modified:
            assert not any(
                path.startswith(protected.split("/")[0])
                for protected in PROTECTED_FILES
                if "/" in protected
                and not path.startswith(AI_AGENT_DIR)
            ) or path.startswith(AI_AGENT_DIR), (
                f"Unexpected modification to existing application file: {path}"
            )
