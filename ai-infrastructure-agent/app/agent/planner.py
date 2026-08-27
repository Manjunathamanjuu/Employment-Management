"""Request-aware investigation planner.

Selects EXISTING allowlisted tools from the user's request.
The LLM may only return tool names from the allowlist — never shell commands.

If the LLM is unavailable or fails, a deterministic heuristic is used.
Unknown or destructive tool names are discarded.
"""

from __future__ import annotations

import json
import os
import re
from typing import Iterable, Optional

from app.agent.state import InvestigationPlan, InvestigationStep
from app.logging.logger import get_logger
from app.tools.docker import DOCKER_TOOLS
from app.tools.gcp import GCP_TOOLS
from app.tools.kubernetes import KUBERNETES_TOOLS
from app.tools.terraform import TERRAFORM_TOOLS

logger = get_logger("ai_agent.planner")


def _cfg():
    """Current settings singleton (avoids a stale import after tests rebind it)."""
    from app import config
    return config.settings


# First-pass tools: no required resource name (except terraform working_directory).
_K8S_DEFAULT = ("get_pods", "get_events", "get_deployment", "get_service")
_K8S_POD = ("get_pods", "get_events", "get_deployment")
_K8S_SERVICE = ("get_service", "get_endpointslices", "get_pods", "get_events")
_K8S_GATEWAY = ("get_gateway", "get_httproute", "get_service", "get_pods")
_DOCKER = ("docker_ps", "docker_images")
_TERRAFORM = ("terraform_validate", "terraform_fmt_check", "terraform_plan")
_GCP = ("gcloud_config_project", "gcloud_list_clusters", "gcloud_describe_cluster")

# Tools that require a discovered resource name — used only as follow-ups.
_FOLLOW_UP_ONLY = frozenset({
    "describe_pod",
    "get_pod_logs",
    "describe_deployment",
    "describe_service",
    "describe_gateway",
    "describe_httproute",
    "docker_inspect",
    "gcloud_describe_instance",
})

ALLOWED_INVESTIGATION_TOOLS: frozenset[str] = frozenset(
    list(KUBERNETES_TOOLS)
    + list(DOCKER_TOOLS)
    + list(GCP_TOOLS)
    + list(TERRAFORM_TOOLS)
)

_SECRET_EXFIL = re.compile(
    r"(show|print|reveal|dump|give|return|what\s+is)\s+"
    r"(me\s+)?(the\s+)?(openai|api[_ -]?key|secret|password|token|private[_ -]?key|credential)",
    re.IGNORECASE,
)

_FAILING_POD_STATUS = re.compile(
    r"CrashLoopBackOff|ImagePullBackOff|ErrImagePull|\bError\b|\bPending\b",
    re.IGNORECASE,
)


def allowed_investigation_tools() -> frozenset[str]:
    return ALLOWED_INVESTIGATION_TOOLS


def is_secret_exfiltration_request(text: str) -> bool:
    return bool(text and _SECRET_EXFIL.search(text))


def filter_allowlisted_tools(names: Iterable[str]) -> list[str]:
    """Keep only existing investigation tools; drop follow-up-only and unknowns."""
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        if not name or not isinstance(name, str):
            continue
        tool = name.strip()
        if tool not in ALLOWED_INVESTIGATION_TOOLS:
            logger.warning(
                "Discarded non-allowlisted tool name",
                extra={"agent_node": "planner", "tool_name": tool, "status": "blocked"},
            )
            continue
        if tool in _FOLLOW_UP_ONLY:
            continue
        if tool in seen:
            continue
        seen.add(tool)
        out.append(tool)
        if len(out) >= _cfg().max_investigation_steps:
            break
    return out


def _heuristic_select_tools(request: str) -> list[str]:
    text = (request or "").lower()
    selected: list[str] = []

    wants_terraform = bool(re.search(r"\bterraform\b|\.tf\b|\btf\s+plan\b", text))
    wants_docker = bool(re.search(r"\bdocker\b", text))
    wants_gcp = bool(re.search(r"\bgcp\b|\bgke\b|\bgcloud\b|google cloud|compute engine", text))
    wants_gateway = bool(re.search(r"\bgateway\b|\bhttproute\b", text))
    wants_service = bool(re.search(r"\bservice\b|\bendpoints?\b", text))
    wants_pod = bool(re.search(
        r"\bpod\b|\bkubernetes\b|\bk8s\b|crashloop|imagepull|deployment|"
        r"replicaset|namespace|employment.management",
        text,
    ))

    if wants_terraform:
        selected.extend(_TERRAFORM)
    if wants_docker:
        selected.extend(_DOCKER)
    if wants_gcp:
        selected.extend(_GCP)
    if wants_gateway:
        selected.extend(_K8S_GATEWAY)
    elif wants_service and not wants_pod:
        selected.extend(_K8S_SERVICE)
    elif wants_pod:
        if re.search(r"crashloop|imagepull|pod", text):
            selected.extend(_K8S_POD)
        else:
            selected.extend(_K8S_DEFAULT)

    if not selected:
        # Ambiguous infrastructure question — default to cluster health, not every tool.
        selected.extend(_K8S_DEFAULT)

    return filter_allowlisted_tools(selected)


def _llm_available() -> bool:
    if not _cfg().openai_api_key_configured:
        return False
    key = _cfg().openai_api_key or ""
    # Test placeholders must not trigger live OpenAI calls.
    if key.startswith("sk-test") or "placeholder" in key.lower():
        return False
    return True


def _call_openai_for_tools(request: str) -> list[str]:
    """Ask the LLM to pick allowlisted tool names. Never executes commands."""
    from openai import OpenAI

    allow = sorted(t for t in ALLOWED_INVESTIGATION_TOOLS if t not in _FOLLOW_UP_ONLY)
    system = (
        "You are a CloudOps investigation planner. "
        "You do not run infrastructure commands. "
        "You only choose diagnostic tool names from the allowlist. "
        "Never choose apply, destroy, delete, exec, rm, kill, or shell tools. "
        "Never output secrets, API keys, or credentials. "
        "Never invent infrastructure state. "
        "Respond with JSON only: {\"tools\": [\"tool_name\"], \"summary\": \"short plan\"}."
    )
    user = (
        f"Allowlisted tools: {allow}\n"
        f"User request: {request}\n"
        "Select the smallest relevant subset. Do not select every tool."
    )
    client = OpenAI(
        api_key=_cfg().openai_api_key,
        timeout=_cfg().llm_timeout_seconds,
    )
    completion = client.chat.completions.create(
        model=_cfg().openai_model,
        temperature=0,
        max_tokens=400,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = (completion.choices[0].message.content or "").strip()
    data = json.loads(content)
    tools = data.get("tools") or []
    if not isinstance(tools, list):
        return []
    return [str(t) for t in tools]


def select_investigation_tools(request: str) -> list[str]:
    """Select allowlisted tools for this request (LLM with heuristic fallback)."""
    if is_secret_exfiltration_request(request):
        return []

    llm_tools: list[str] = []
    if _llm_available():
        try:
            llm_tools = filter_allowlisted_tools(_call_openai_for_tools(request))
        except Exception as exc:
            logger.warning(
                "LLM planner failed; using heuristic",
                extra={
                    "agent_node": "planner",
                    "status": "llm_fallback",
                    "error_type": type(exc).__name__,
                },
            )
            llm_tools = []

    if llm_tools:
        return llm_tools
    return _heuristic_select_tools(request)


def _step_parameters(tool_name: str, namespace: str) -> dict:
    if tool_name in KUBERNETES_TOOLS:
        params: dict = {"namespace": namespace}
        if _cfg().kubernetes_context:
            params["context"] = _cfg().kubernetes_context
        return params
    if tool_name in DOCKER_TOOLS:
        if tool_name == "docker_ps":
            return {"all_containers": True}
        return {}
    if tool_name in GCP_TOOLS:
        return {}
    if tool_name in TERRAFORM_TOOLS:
        wd = _cfg().terraform_working_directory or os.getcwd()
        return {"working_directory": wd}
    return {}


def build_investigation_plan(
    request: str,
    namespace: Optional[str] = None,
) -> InvestigationPlan:
    """Build an InvestigationPlan using allowlisted tools only."""
    ns = namespace or _cfg().kubernetes_namespace
    if is_secret_exfiltration_request(request):
        return InvestigationPlan(
            summary=(
                "Secret disclosure is not permitted. "
                "No credentials or API keys will be returned."
            ),
            steps=[],
            estimated_tools=[],
        )

    tools = select_investigation_tools(request)
    descriptions = {
        "get_pods": "List pods in the namespace",
        "get_events": "Collect recent Kubernetes events",
        "get_deployment": "List deployments",
        "get_service": "List services",
        "get_replicasets": "List replica sets",
        "get_endpointslices": "List EndpointSlices",
        "get_gateway": "List Gateway resources",
        "get_httproute": "List HTTPRoutes",
        "docker_ps": "List Docker containers",
        "docker_images": "List Docker images",
        "terraform_validate": "Validate Terraform configuration",
        "terraform_fmt_check": "Check Terraform formatting",
        "terraform_plan": "Run Terraform plan (read-only)",
        "gcloud_config_project": "Read active GCP project",
        "gcloud_list_clusters": "List GKE clusters",
        "gcloud_describe_cluster": "Describe the configured GKE cluster",
    }
    steps = [
        InvestigationStep(
            description=descriptions.get(name, f"Run {name}"),
            tool=name,
            parameters=_step_parameters(name, ns),
        )
        for name in tools
    ]
    summary = (
        f"Investigate: '{(request or '')[:100]}'. "
        f"Selected {len(steps)} allowlisted diagnostic tool(s)."
    )
    return InvestigationPlan(
        summary=summary,
        steps=steps,
        estimated_tools=tools,
    )


def parse_failing_pod_names(stdout: str) -> list[str]:
    """Extract failing pod names from kubectl get pods output."""
    if not stdout:
        return []
    names: list[str] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped or stripped.upper().startswith("NAME"):
            continue
        if not _FAILING_POD_STATUS.search(stripped):
            continue
        name = stripped.split()[0]
        if name and name not in names:
            names.append(name)
        if len(names) >= 3:
            break
    return names


def follow_up_steps(
    tool_results: list,
    existing_tools: Iterable[str],
    namespace: Optional[str] = None,
) -> list[InvestigationStep]:
    """Add describe/logs only after a resource name is observed."""
    ns = namespace or _cfg().kubernetes_namespace
    already = set(existing_tools)
    extra: list[InvestigationStep] = []
    for result in tool_results:
        if getattr(result, "tool_name", None) != "get_pods":
            continue
        stdout = getattr(result, "stdout", None) or ""
        for pod_name in parse_failing_pod_names(stdout):
            if "describe_pod" not in already:
                extra.append(InvestigationStep(
                    description=f"Describe failing pod {pod_name}",
                    tool="describe_pod",
                    parameters={"pod_name": pod_name, "namespace": ns},
                ))
                already.add("describe_pod")
            if "get_pod_logs" not in already:
                extra.append(InvestigationStep(
                    description=f"Collect logs for failing pod {pod_name}",
                    tool="get_pod_logs",
                    parameters={
                        "pod_name": pod_name,
                        "namespace": ns,
                        "tail_lines": 100,
                        "previous": True,
                    },
                ))
                already.add("get_pod_logs")
    return extra[: max(0, _cfg().max_investigation_steps)]
