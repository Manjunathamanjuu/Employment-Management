"""Read-only Docker diagnostic tools.

Allowed:  docker images, docker ps, docker inspect
Blocked:  docker rm, docker rmi, docker kill, docker system prune
          (and all other mutating operations)

All validation is performed before subprocess execution.
shell=False is enforced throughout.
"""

from __future__ import annotations

import re
from typing import Optional

from app.agent.state import ToolResult
from app.tools.base import BaseTool, _DANGEROUS_CHARS

# ---------------------------------------------------------------------------
# Docker-specific constants
# ---------------------------------------------------------------------------

# Allowed Docker subcommands (read-only)
DOCKER_ALLOWED_COMMANDS = frozenset({"images", "ps", "inspect"})

# Explicitly blocked Docker subcommands
DOCKER_BLOCKED_COMMANDS = frozenset({
    "rm",
    "rmi",
    "kill",
    "stop",
    "start",
    "restart",
    "pause",
    "unpause",
    "create",
    "run",
    "exec",
    "build",
    "push",
    "pull",
    "tag",
    "save",
    "load",
    "import",
    "export",
    "commit",
    "system",
    "network",
    "volume",
    "swarm",
    "service",
    "stack",
    "secret",
    "config",
    "container",
    "image",
    "prune",
    "update",
    "rename",
    "cp",
    "attach",
    "wait",
    "port",
    "diff",
    "top",
})

# Docker image name: allow registry/repo:tag format
_DOCKER_IMAGE_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9\.\-\_\/\:@]{0,255}$"
)

# Docker container ID or name
_DOCKER_CONTAINER_PATTERN = re.compile(
    r"^[a-zA-Z0-9][a-zA-Z0-9\.\-\_]{0,127}$"
)


def validate_docker_command(command: str) -> str:
    """Ensure only allowlisted Docker commands are used."""
    if command in DOCKER_BLOCKED_COMMANDS:
        raise ValueError(
            f"Docker command '{command}' is explicitly blocked. "
            f"Allowed: {sorted(DOCKER_ALLOWED_COMMANDS)}"
        )
    if command not in DOCKER_ALLOWED_COMMANDS:
        raise ValueError(
            f"Docker command '{command}' is not in the allowlist. "
            f"Allowed: {sorted(DOCKER_ALLOWED_COMMANDS)}"
        )
    return command


def validate_docker_image(image: str) -> str:
    """Validate a Docker image name/tag."""
    if not image or not isinstance(image, str):
        raise ValueError("Docker image name must be a non-empty string")
    image = image.strip()
    if _DANGEROUS_CHARS.search(image):
        raise ValueError(f"Docker image name contains invalid characters: {image!r}")
    if not _DOCKER_IMAGE_PATTERN.match(image):
        raise ValueError(f"Invalid Docker image name: {image!r}")
    return image


def validate_docker_container(container: str) -> str:
    """Validate a Docker container ID or name."""
    if not container or not isinstance(container, str):
        raise ValueError("Container ID/name must be a non-empty string")
    container = container.strip()
    if _DANGEROUS_CHARS.search(container):
        raise ValueError(
            f"Container ID/name contains invalid characters: {container!r}"
        )
    if not _DOCKER_CONTAINER_PATTERN.match(container):
        raise ValueError(f"Invalid Docker container ID/name: {container!r}")
    return container


# ---------------------------------------------------------------------------
# Docker tools
# ---------------------------------------------------------------------------


class DockerImages(BaseTool):
    """List Docker images on the host."""

    tool_name = "docker_images"

    def execute(
        self,
        repository: Optional[str] = None,
        all_images: bool = False,
        **kwargs,
    ) -> ToolResult:
        validate_docker_command("images")
        cmd = ["docker", "images", "--format",
               "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}\t{{.Size}}"]
        if repository:
            repo = validate_docker_image(repository)
            cmd.append(repo)
        if all_images:
            cmd.append("--all")
        return self._run_subprocess(cmd, command_type="read")


class DockerPs(BaseTool):
    """List Docker containers (running and optionally stopped)."""

    tool_name = "docker_ps"

    def execute(
        self,
        all_containers: bool = False,
        **kwargs,
    ) -> ToolResult:
        validate_docker_command("ps")
        cmd = ["docker", "ps", "--format",
               "table {{.ID}}\t{{.Image}}\t{{.Command}}\t{{.Status}}\t{{.Names}}"]
        if all_containers:
            cmd.append("--all")
        return self._run_subprocess(cmd, command_type="read")


class DockerInspect(BaseTool):
    """Inspect a Docker container or image."""

    tool_name = "docker_inspect"

    def execute(
        self,
        target: str,
        inspect_type: str = "container",
        **kwargs,
    ) -> ToolResult:
        validate_docker_command("inspect")
        if inspect_type not in ("container", "image"):
            raise ValueError(
                f"inspect_type must be 'container' or 'image', got: {inspect_type!r}"
            )
        if inspect_type == "container":
            name = validate_docker_container(target)
        else:
            name = validate_docker_image(target)

        cmd = ["docker", "inspect", "--type", inspect_type, name]
        return self._run_subprocess(
            cmd, command_type="read", resource=name
        )


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

DOCKER_TOOLS: dict[str, type[BaseTool]] = {
    "docker_images": DockerImages,
    "docker_ps": DockerPs,
    "docker_inspect": DockerInspect,
}


def get_docker_tool(tool_name: str, timeout: int = 30) -> BaseTool:
    """Factory: return an instantiated Docker tool by name."""
    cls = DOCKER_TOOLS.get(tool_name)
    if cls is None:
        raise ValueError(
            f"Unknown Docker tool: {tool_name!r}. "
            f"Available: {sorted(DOCKER_TOOLS.keys())}"
        )
    return cls(timeout=timeout)
