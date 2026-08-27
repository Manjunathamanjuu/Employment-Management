"""Tests for the AI Infrastructure Agent Dockerfile.

These tests parse and verify Dockerfile security and structure properties
without requiring Docker to be installed.

Verifies:
- Production Python base image (pinned, not :latest)
- Non-root user (uid 1000)
- No credentials, secrets, or .env baked in
- Health check configured
- tini for PID 1 / signal handling
- No :latest tag on any FROM instruction
- Correct EXPOSE port
- All configuration via ENV (no hard-coded secrets)
- Multi-stage build (builder + runtime)
- Non-root USER instruction present
- .dockerignore excludes secrets
"""

from __future__ import annotations

import os
import re

import pytest

pytestmark = pytest.mark.unit

DOCKERFILE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "Dockerfile"
)
DOCKERIGNORE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", ".dockerignore"
)
ROOT_DOCKERFILE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "Dockerfile"
)


def _read_dockerfile() -> str:
    with open(DOCKERFILE_PATH) as f:
        return f.read()


def _read_dockerignore() -> str:
    with open(DOCKERIGNORE_PATH) as f:
        return f.read()


# ---------------------------------------------------------------------------
# Dockerfile exists and is readable
# ---------------------------------------------------------------------------

class TestDockerfileExists:
    def test_dockerfile_exists(self):
        assert os.path.exists(DOCKERFILE_PATH), (
            f"ai-infrastructure-agent/Dockerfile not found at {DOCKERFILE_PATH}"
        )

    def test_dockerfile_not_empty(self):
        content = _read_dockerfile()
        assert len(content) > 100


# ---------------------------------------------------------------------------
# Base image — no :latest
# ---------------------------------------------------------------------------

class TestBaseImage:
    def test_no_latest_tag_on_any_from(self):
        content = _read_dockerfile()
        from_lines = [l.strip() for l in content.splitlines()
                      if l.strip().upper().startswith("FROM")]
        for line in from_lines:
            assert ":latest" not in line, (
                f"FROM uses :latest tag (forbidden in production): {line}"
            )

    def test_uses_python_slim_image(self):
        content = _read_dockerfile()
        # Should use python:X.Y-slim or similar slim variant
        assert re.search(r"FROM\s+python:3\.\d+[-\w]*slim", content), (
            "Dockerfile should use a slim Python base image for minimal surface area"
        )

    def test_uses_python_312(self):
        content = _read_dockerfile()
        assert "python:3.12" in content, (
            "Dockerfile should target Python 3.12"
        )

    def test_multi_stage_build(self):
        content = _read_dockerfile()
        from_count = len(re.findall(r"^\s*FROM\s+", content, re.MULTILINE))
        assert from_count >= 2, (
            "Dockerfile should use multi-stage build (builder + runtime) "
            f"but found only {from_count} FROM instruction(s)"
        )


# ---------------------------------------------------------------------------
# Non-root user
# ---------------------------------------------------------------------------

class TestNonRootUser:
    def test_non_root_user_created(self):
        content = _read_dockerfile()
        assert re.search(r"useradd|adduser", content), (
            "Dockerfile must create a non-root user"
        )

    def test_user_instruction_switches_to_non_root(self):
        content = _read_dockerfile()
        user_matches = re.findall(r"^\s*USER\s+(\S+)", content, re.MULTILINE)
        assert len(user_matches) > 0, "Dockerfile must have a USER instruction"
        # The last USER instruction should not be root
        last_user = user_matches[-1].lower()
        assert last_user not in ("root", "0"), (
            f"Container must not run as root. Last USER instruction: {last_user}"
        )

    def test_uid_1000_used(self):
        content = _read_dockerfile()
        assert "1000" in content, (
            "Dockerfile should create user with uid 1000"
        )


# ---------------------------------------------------------------------------
# No credentials in image
# ---------------------------------------------------------------------------

class TestNoCredentialsInImage:
    FORBIDDEN_PATTERNS = [
        re.compile(r"sk-[A-Za-z0-9]{20,}", re.I),           # OpenAI key
        re.compile(r"OPENAI_API_KEY\s*=\s*sk-", re.I),       # Set real key
        re.compile(r"password\s*=\s*\S{4,}", re.I),
        re.compile(r"AIza[0-9A-Za-z\-_]{35}"),                # GCP API key
        re.compile(r"-----BEGIN.*PRIVATE KEY"),
        re.compile(r"COPY\s+.*\.env\s"),                       # Copying .env
        re.compile(r"COPY\s+.*\.key\s"),                       # Copying key files
        re.compile(r"COPY\s+.*credentials"),
        re.compile(r"ADD\s+.*secret"),
    ]

    def test_no_hardcoded_secrets(self):
        content = _read_dockerfile()
        for pattern in self.FORBIDDEN_PATTERNS:
            match = pattern.search(content)
            assert match is None, (
                f"Dockerfile contains a forbidden secret pattern: "
                f"'{match.group(0)[:50]}'"
            )

    def test_no_env_file_copied(self):
        content = _read_dockerfile()
        assert not re.search(r"COPY\s+\.env", content), (
            "Dockerfile must not COPY a .env file into the image"
        )

    def test_openai_key_env_has_no_value(self):
        content = _read_dockerfile()
        # OPENAI_API_KEY should either not be set or have an empty value
        match = re.search(r"ENV.*OPENAI_API_KEY\s*=\s*(\S+)", content)
        if match:
            value = match.group(1)
            assert value in ("", '""', "''"), (
                f"OPENAI_API_KEY in ENV must be empty, got: {value}"
            )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_healthcheck_instruction_present(self):
        content = _read_dockerfile()
        assert "HEALTHCHECK" in content, (
            "Dockerfile must include a HEALTHCHECK instruction for Kubernetes probes"
        )

    def test_healthcheck_uses_health_endpoint(self):
        content = _read_dockerfile()
        assert re.search(r"HEALTHCHECK.*health", content, re.IGNORECASE | re.DOTALL), (
            "HEALTHCHECK should target the /health endpoint"
        )

    def test_healthcheck_has_interval(self):
        content = _read_dockerfile()
        assert "--interval" in content, "HEALTHCHECK should specify --interval"

    def test_healthcheck_has_timeout(self):
        content = _read_dockerfile()
        assert "--timeout" in content, "HEALTHCHECK should specify --timeout"

    def test_healthcheck_has_retries(self):
        content = _read_dockerfile()
        assert "--retries" in content, "HEALTHCHECK should specify --retries"


# ---------------------------------------------------------------------------
# Signal handling (tini / PID 1)
# ---------------------------------------------------------------------------

class TestSignalHandling:
    def test_tini_installed(self):
        content = _read_dockerfile()
        assert "tini" in content.lower(), (
            "Dockerfile should install tini for correct PID 1 signal handling"
        )

    def test_tini_as_entrypoint(self):
        content = _read_dockerfile()
        assert re.search(r'ENTRYPOINT\s+\[.*tini', content), (
            "ENTRYPOINT should use tini for proper signal forwarding"
        )

    def test_uvicorn_in_cmd(self):
        content = _read_dockerfile()
        assert "uvicorn" in content, (
            "CMD should launch uvicorn as the production ASGI server"
        )


# ---------------------------------------------------------------------------
# Port exposure
# ---------------------------------------------------------------------------

class TestPortExposure:
    def test_expose_8080(self):
        content = _read_dockerfile()
        assert re.search(r"EXPOSE\s+8080", content), (
            "Dockerfile must EXPOSE port 8080"
        )


# ---------------------------------------------------------------------------
# Environment variables (no sensitive defaults)
# ---------------------------------------------------------------------------

class TestEnvironmentVariables:
    def test_debug_default_false(self):
        content = _read_dockerfile()
        assert re.search(r"DEBUG\s*=\s*false", content, re.I), (
            "DEBUG should default to false in production"
        )

    def test_environment_default_production(self):
        content = _read_dockerfile()
        assert re.search(r"ENVIRONMENT\s*=\s*production", content, re.I), (
            "ENVIRONMENT should default to production"
        )

    def test_require_human_approval_default_true(self):
        content = _read_dockerfile()
        assert re.search(r"REQUIRE_HUMAN_APPROVAL\s*=\s*true", content, re.I), (
            "REQUIRE_HUMAN_APPROVAL must default to true in production image"
        )

    def test_pythonunbuffered_set(self):
        content = _read_dockerfile()
        assert "PYTHONUNBUFFERED=1" in content, (
            "PYTHONUNBUFFERED=1 required for real-time log output"
        )


# ---------------------------------------------------------------------------
# .dockerignore
# ---------------------------------------------------------------------------

class TestDockerignore:
    def test_dockerignore_exists(self):
        assert os.path.exists(DOCKERIGNORE_PATH), (
            "ai-infrastructure-agent/.dockerignore must exist"
        )

    def test_env_excluded(self):
        content = _read_dockerignore()
        assert ".env" in content, ".dockerignore must exclude .env"

    def test_tests_excluded(self):
        content = _read_dockerignore()
        assert "tests/" in content, ".dockerignore should exclude tests/"

    def test_git_excluded(self):
        content = _read_dockerignore()
        assert ".git" in content, ".dockerignore should exclude .git"

    def test_pycache_excluded(self):
        content = _read_dockerignore()
        assert "__pycache__" in content or "*.pyc" in content

    def test_private_key_excluded(self):
        content = _read_dockerignore()
        assert "*.key" in content or "*.pem" in content, (
            ".dockerignore should exclude private key files"
        )

    def test_credentials_excluded(self):
        content = _read_dockerignore()
        assert "gcp-credentials.json" in content or "credentials" in content.lower()


# ---------------------------------------------------------------------------
# Existing Employment Management Dockerfile unchanged
# ---------------------------------------------------------------------------

class TestExistingDockerfileUnchanged:
    def test_root_dockerfile_exists(self):
        workspace_dockerfile = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "Dockerfile"
        )
        assert os.path.exists(workspace_dockerfile), (
            "Root Dockerfile (Employment Management) must still exist"
        )

    def test_root_dockerfile_is_java_app(self):
        workspace_dockerfile = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "Dockerfile"
        )
        with open(workspace_dockerfile) as f:
            content = f.read()
        assert any(kw in content for kw in
                   ("maven", "java", "JAVA", "openjdk", "eclipse-temurin",
                    "jar", "JAR")), (
            "Root Dockerfile must still be for the Java Employment Management app"
        )

    def test_agent_dockerfile_separate_from_root(self):
        agent_df = DOCKERFILE_PATH
        root_df = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "Dockerfile"
        )
        assert os.path.realpath(agent_df) != os.path.realpath(root_df), (
            "Agent Dockerfile must be separate from root Dockerfile"
        )

    def test_agent_dockerfile_uses_python_not_java(self):
        content = _read_dockerfile()
        assert "python" in content.lower(), "Agent Dockerfile must use Python"
        # Must not accidentally use the Java stack
        assert "eclipse-temurin" not in content
        assert "spring" not in content.lower()
