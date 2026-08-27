"""LangGraph node implementations.

Each node receives the full AgentState, performs one focused responsibility,
and returns a dict of updated state fields. The LLM reasons; tools execute.

Phase 2: nodes use mocked infrastructure evidence.
Phase 3+: real tool calls wired in.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.agent.state import (
    AgentState,
    ApprovalStatus,
    ConfidenceLevel,
    EvidenceItem,
    FinalReport,
    InvestigationPlan,
    InvestigationStatus,
    InvestigationStep,
    RemediationAction,
    RemediationPlan,
    RiskLevel,
    RootCauseAnalysis,
    ToolResult,
    VerificationResult,
)
from app.config import settings
from app.logging.logger import AgentLogger


def _make_logger(state: AgentState, node: str) -> AgentLogger:
    return AgentLogger(
        f"ai_agent.nodes.{node}",
        request_id=state.request_id,
        agent_node=node,
    )


# ---------------------------------------------------------------------------
# Node: request_analyzer
# ---------------------------------------------------------------------------


def request_analyzer(state: AgentState) -> dict[str, Any]:
    """Parse and validate the incoming user request.

    Enriches the state with a sanitised request and transitions to INVESTIGATING.
    The LLM is NOT called here — this is a lightweight structural pass.
    """
    log = _make_logger(state, "request_analyzer")
    log.info("Analyzing request", status="started")

    errors: list[str] = list(state.errors)

    request_text = (state.user_request or "").strip()
    if not request_text:
        errors.append("User request is empty.")
        log.error("Empty request", status="failed")
        return {
            "status": InvestigationStatus.FAILED,
            "errors": errors,
        }

    if len(request_text) > 2000:
        # Truncate rather than hard-fail — log the truncation
        request_text = request_text[:2000]
        log.warning("Request truncated to 2000 characters", status="warning")

    log.info("Request accepted", status="completed")
    return {
        "user_request": request_text,
        "status": InvestigationStatus.INVESTIGATING,
        "current_step": 1,
    }


# ---------------------------------------------------------------------------
# Node: investigation_planner
# ---------------------------------------------------------------------------


def investigation_planner(state: AgentState) -> dict[str, Any]:
    """Generate an investigation plan.

    In Phase 2 this produces a deterministic mock plan.
    Phase 3+ will call the LLM with the user request to produce a real plan.
    """
    log = _make_logger(state, "investigation_planner")
    log.info("Planning investigation", status="started")

    # Phase 2 mock plan — deterministic, no LLM call.
    # Note: tools requiring a specific resource name (describe_pod, get_pod_logs)
    # are added dynamically in Phase 5+ once pod names are discovered.
    steps = [
        InvestigationStep(
            description="List pods in namespace",
            tool="get_pods",
            parameters={"namespace": settings.kubernetes_namespace},
        ),
        InvestigationStep(
            description="Check recent Kubernetes events",
            tool="get_events",
            parameters={"namespace": settings.kubernetes_namespace},
        ),
        InvestigationStep(
            description="List deployments in namespace",
            tool="get_deployment",
            parameters={"namespace": settings.kubernetes_namespace},
        ),
        InvestigationStep(
            description="List services in namespace",
            tool="get_service",
            parameters={"namespace": settings.kubernetes_namespace},
        ),
    ]

    plan = InvestigationPlan(
        summary=(
            f"Investigate infrastructure issue: '{state.user_request[:100]}'. "
            "Collect pod status, events, deployments, and services "
            "from the employment-management namespace."
        ),
        steps=steps,
        estimated_tools=["get_pods", "get_events", "get_deployment", "get_service"],
    )

    log.info(
        f"Investigation plan created with {len(steps)} steps",
        status="completed",
    )
    return {
        "investigation_plan": plan,
        "current_step": 2,
    }


# ---------------------------------------------------------------------------
# Node: tool_executor
# ---------------------------------------------------------------------------


def tool_executor(state: AgentState) -> dict[str, Any]:
    """Execute all pending investigation steps.

    Routes each step to the appropriate tool:
    - Kubernetes tools: get_pods, describe_pod, get_pod_logs, get_events,
      get_deployment, describe_deployment, get_replicasets, get_service,
      describe_service, get_endpointslices, get_gateway, describe_gateway,
      get_httproute, describe_httproute
    - Unrecognised tools: fall back to mock (Phase 2 compatibility)
    """
    from app.tools.kubernetes import KUBERNETES_TOOLS, get_kubernetes_tool
    from app.tools.docker import DOCKER_TOOLS, get_docker_tool
    from app.tools.gcp import GCP_TOOLS, get_gcp_tool
    from app.tools.terraform import TERRAFORM_TOOLS, get_terraform_tool

    ALL_TOOLS = {**KUBERNETES_TOOLS, **DOCKER_TOOLS, **GCP_TOOLS, **TERRAFORM_TOOLS}

    log = _make_logger(state, "tool_executor")

    plan = state.investigation_plan
    if not plan or not plan.steps:
        log.warning("No investigation plan or steps available", status="skipped")
        return {"current_step": state.current_step + 1}

    tool_results: list[ToolResult] = list(state.tool_results)

    for step in plan.steps:
        if step.status != "PENDING":
            continue

        tool_name = step.tool or "unknown"
        log.info(
            f"Executing step: {step.description}",
            tool_name=tool_name,
            status="executing",
            execution_time=0.0,
        )

        try:
            if tool_name in KUBERNETES_TOOLS:
                tool = get_kubernetes_tool(tool_name, timeout=settings.tool_timeout_seconds)
                result = tool.execute(**step.parameters)
            elif tool_name in DOCKER_TOOLS:
                tool = get_docker_tool(tool_name, timeout=settings.tool_timeout_seconds)
                result = tool.execute(**step.parameters)
            elif tool_name in GCP_TOOLS:
                tool = get_gcp_tool(tool_name, timeout=settings.tool_timeout_seconds)
                result = tool.execute(**step.parameters)
            elif tool_name in TERRAFORM_TOOLS:
                tool = get_terraform_tool(tool_name, timeout=settings.tool_timeout_seconds)
                result = tool.execute(**step.parameters)
            else:
                # Phase 2 mock fallback for tools not yet implemented
                result = _mock_tool_result(tool_name, step.parameters)
        except (ValueError, TypeError) as exc:
            result = ToolResult(
                tool_name=tool_name,
                status="validation_error",
                command_type="read",
                error=str(exc),
                namespace=step.parameters.get("namespace"),
            )

        step.status = "COMPLETED"
        step.result = result
        tool_results.append(result)
        log.tool_call(
            tool_name=tool_name,
            status=result.status,
            execution_time=result.duration or 0.0,
        )

    return {
        "tool_results": tool_results,
        "investigation_plan": plan,
        "current_step": state.current_step + 1,
    }


def _mock_tool_result(tool_name: str, params: dict) -> ToolResult:
    """Return deterministic mock output for each tool type."""
    ns = params.get("namespace", "employment-management")
    ts = datetime.now(timezone.utc)

    mock_outputs: dict[str, dict] = {
        "get_pods": {
            "stdout": (
                "NAME                                    READY   STATUS             RESTARTS   AGE\n"
                "employment-management-6d8f9b7c4-xkp2n   0/1     CrashLoopBackOff   5          10m"
            ),
            "exit_code": 0,
        },
        "describe_pod": {
            "stdout": (
                "Name: employment-management-6d8f9b7c4-xkp2n\n"
                "Namespace: employment-management\n"
                "Status: Running\n"
                "Containers:\n"
                "  employment-management:\n"
                "    State: Waiting\n"
                "      Reason: CrashLoopBackOff\n"
                "    Last State: Terminated\n"
                "      Reason: Error\n"
                "      Exit Code: 1\n"
                "    Ready: False\n"
                "    Restart Count: 5\n"
                "Conditions:\n"
                "  Ready: False\n"
                "Events:\n"
                "  Warning  BackOff  pod/employment-management-6d8f9b7c4-xkp2n  "
                "Back-off restarting failed container"
            ),
            "exit_code": 0,
        },
        "get_pod_logs": {
            "stdout": (
                "2026-08-27T10:00:00Z INFO  Starting Employment Management Application\n"
                "2026-08-27T10:00:01Z ERROR Failed to connect to database: Connection refused\n"
                "2026-08-27T10:00:01Z ERROR Application startup failed\n"
                "2026-08-27T10:00:01Z FATAL Exiting with code 1"
            ),
            "exit_code": 0,
        },
        "get_events": {
            "stdout": (
                "LAST SEEN   TYPE      REASON      OBJECT                                      MESSAGE\n"
                "10m         Warning   BackOff     pod/employment-management-6d8f9b7c4-xkp2n  "
                "Back-off restarting failed container employment-management in pod\n"
                "10m         Warning   Failed      pod/employment-management-6d8f9b7c4-xkp2n  "
                "Error: failed to create containerd task: failed to create shim: "
                "OCI runtime create failed"
            ),
            "exit_code": 0,
        },
    }

    mock = mock_outputs.get(
        tool_name,
        {"stdout": f"Mock output for {tool_name}", "exit_code": 0},
    )

    return ToolResult(
        tool_name=tool_name,
        status="success",
        command_type="read",
        namespace=ns,
        stdout=mock["stdout"],
        exit_code=mock["exit_code"],
        duration=0.15,
        timestamp=ts,
    )


# ---------------------------------------------------------------------------
# Node: evidence_analyzer
# ---------------------------------------------------------------------------


def evidence_analyzer(state: AgentState) -> dict[str, Any]:
    """Extract and correlate structured evidence from tool results.

    Uses EvidenceCollector to:
    - Apply 11 incident-type pattern extractors
    - Generate cross-signal inferences (clearly flagged)
    - Detect conflicting signals
    - Identify missing evidence
    - Calculate overall confidence
    """
    from app.analysis.evidence import EvidenceCollector

    log = _make_logger(state, "evidence_analyzer")
    log.info("Analyzing evidence", status="started")

    collector = EvidenceCollector()
    correlation = collector.collect(state.tool_results)

    # Merge with any existing evidence (e.g. from previous phases)
    existing_evidence = list(state.evidence)
    merged_evidence = existing_evidence + correlation.evidence

    existing_issues = list(state.issues)
    merged_issues = list(dict.fromkeys(existing_issues + correlation.issues))

    if correlation.conflicting_signals:
        log.warning(
            f"Conflicting signals detected: {correlation.conflicting_signals}",
            status="conflicts",
        )
    if correlation.missing_evidence:
        log.info(
            f"Missing evidence identified: {correlation.missing_evidence}",
            status="missing_evidence",
        )

    log.info(
        f"Evidence analysis complete: {len(merged_evidence)} items, "
        f"{len(merged_issues)} issues, confidence={correlation.overall_confidence.value}",
        status="completed",
    )
    return {
        "evidence": merged_evidence,
        "issues": merged_issues,
        "current_step": state.current_step + 1,
    }


# ---------------------------------------------------------------------------
# Node: root_cause_analyzer
# ---------------------------------------------------------------------------


def _infer_incident_types_from_evidence(evidence: list) -> list[str]:
    """Infer incident types from evidence observation text.

    Used when tool_results is empty but evidence items exist (e.g. in unit tests
    that pre-populate state.evidence directly).
    """
    import re
    types = set()
    patterns = [
        (re.compile(r"CrashLoopBackOff", re.I), "CrashLoopBackOff"),
        (re.compile(r"ImagePullBackOff|ErrImagePull", re.I), "ImagePullBackOff"),
        (re.compile(r"Readiness probe", re.I), "ReadinessFailure"),
        (re.compile(r"Liveness probe", re.I), "LivenessFailure"),
        (re.compile(r"no.{0,20}endpoint|Endpoints.*none", re.I), "ServiceNoEndpoints"),
        (re.compile(r"Gateway.*not|Programmed.*False", re.I), "GatewayFailure"),
        (re.compile(r"HTTPRoute|Accepted.*False", re.I), "HTTPRouteFailure"),
        (re.compile(r"unavailable.{0,20}replica|MinimumReplicas", re.I), "DeploymentUnavailable"),
        (re.compile(r"OCI runtime|Docker|containerd", re.I), "DockerIssue"),
        (re.compile(r"terraform|Terraform", re.I), "TerraformIssue"),
        (re.compile(r"Connection refused|ECONNREFUSED", re.I), "ConnectionRefused"),
        (re.compile(r"exit.{0,20}code.{0,10}[1-9]", re.I), "CrashLoopBackOff"),
    ]
    for ev in evidence:
        if ev.is_inference:
            continue
        for pattern, incident_type in patterns:
            if pattern.search(ev.observation):
                types.add(incident_type)
    return list(types)


def root_cause_analyzer(state: AgentState) -> dict[str, Any]:
    """Determine probable root cause from correlated evidence.

    Uses RootCauseEngine which:
    - Maps incident types to structured templates (no hallucination)
    - Requires confirmed evidence for any non-INSUFFICIENT confidence
    - Downgrades confidence on conflicting signals
    - Returns INSUFFICIENT explicitly when evidence is absent
    """
    from app.analysis.evidence import EvidenceCollector
    from app.analysis.root_cause import RootCauseEngine

    log = _make_logger(state, "root_cause_analyzer")
    log.info("Running root cause analysis", status="started")

    # Re-run correlation to get full CorrelationResult with incident_types,
    # conflicts, and missing_evidence
    collector = EvidenceCollector()
    correlation = collector.collect(state.tool_results)

    # Supplement with pre-existing evidence items already in state
    if state.evidence:
        existing_confirmed = [e for e in state.evidence if not e.is_inference]
        corr_confirmed = [e for e in correlation.evidence if not e.is_inference]
        seen = {e.observation for e in corr_confirmed}
        for e in existing_confirmed:
            if e.observation not in seen:
                correlation.evidence.append(e)
                seen.add(e.observation)

    # When tool_results were empty (e.g. tests that pre-populate state.evidence),
    # infer incident types from existing evidence observations so the engine
    # can select the right template
    if not correlation.incident_types and correlation.evidence:
        correlation.incident_types = _infer_incident_types_from_evidence(
            correlation.evidence
        )

    engine = RootCauseEngine()
    rca = engine.analyze(correlation, user_request=state.user_request)

    log.info(
        f"Root cause analysis complete: confidence={rca.confidence.value}, "
        f"incident_status={rca.incident_status}",
        status="completed",
    )
    return {
        "root_cause": rca,
        "confidence": rca.confidence,
        "risk": rca.risk,
        "status": InvestigationStatus.ANALYZED,
        "current_step": state.current_step + 1,
    }

def remediation_planner(state: AgentState) -> dict[str, Any]:
    """Generate remediation recommendations grounded in root cause analysis.

    Uses RemediationPlanner which:
    - Selects an incident-specific playbook from the root cause
    - Filters dangerous actions (safety net)
    - Enforces approval_required=True on every action
    - Returns advisory-only plan when confidence is LOW
    - Returns no plan when confidence is INSUFFICIENT
    - Every action includes a rollback plan
    """
    from app.analysis.remediation import RemediationPlanner

    log = _make_logger(state, "remediation_planner")
    log.info("Planning remediation", status="started")

    if not state.root_cause or state.confidence == ConfidenceLevel.INSUFFICIENT:
        log.warning("Skipping remediation planning — insufficient confidence", status="skipped")
        return {
            "status": InvestigationStatus.REMEDIATION_PLANNED,
            "current_step": state.current_step + 1,
        }

    planner = RemediationPlanner()
    plan = planner.plan(
        root_cause=state.root_cause,
        namespace=settings.kubernetes_namespace,
        confidence=state.confidence,
    )

    if plan is None:
        log.warning("No remediation plan generated", status="no_plan")
        return {
            "status": InvestigationStatus.REMEDIATION_PLANNED,
            "current_step": state.current_step + 1,
        }

    log.info(
        f"Remediation plan: {len(plan.actions)} actions, risk={plan.overall_risk.value}",
        status="completed",
    )
    return {
        "remediation_plan": plan,
        "risk": plan.overall_risk,
        "status": InvestigationStatus.REMEDIATION_PLANNED,
        "approval_required": True,
        "approval_status": ApprovalStatus.PENDING,
        "current_step": state.current_step + 1,
    }



# ---------------------------------------------------------------------------
# Node: approval_gate
# ---------------------------------------------------------------------------


def approval_gate(state: AgentState) -> dict[str, Any]:
    """Enforce human approval before any remediation executes.

    PENDING → stop workflow.
    APPROVED → allow remediation_executor.
    REJECTED → skip to final_report.
    Fail closed: any non-APPROVED status blocks execution.
    """
    log = _make_logger(state, "approval_gate")
    log.info(
        f"Approval gate: status={state.approval_status.value}",
        status="checking",
    )

    approval_status = state.approval_status

    if approval_status == ApprovalStatus.PENDING:
        log.info("Approval pending — workflow paused at approval gate", status="waiting")
        return {
            "status": InvestigationStatus.AWAITING_APPROVAL,
            "current_step": state.current_step + 1,
        }

    if approval_status == ApprovalStatus.APPROVED:
        log.info("Remediation approved", status="approved")
        return {
            "status": InvestigationStatus.REMEDIATION_APPROVED,
            "current_step": state.current_step + 1,
        }

    # REJECTED or any other value — fail closed
    log.warning(
        f"Remediation not approved (status={approval_status.value}) — skipping execution",
        status="rejected",
    )
    return {
        "status": InvestigationStatus.REMEDIATION_REJECTED,
        "current_step": state.current_step + 1,
    }


# ---------------------------------------------------------------------------
# Node: remediation_executor
# ---------------------------------------------------------------------------


def remediation_executor(state: AgentState) -> dict[str, Any]:
    """Execute ONLY approved and allowlisted remediation actions.

    Phase 2: stub — logs the intent but does not call real tools.
    Phase 9+: real allowlisted execution with audit trail.
    """
    log = _make_logger(state, "remediation_executor")

    # Hard safety check — must never execute without APPROVED status
    if state.approval_status != ApprovalStatus.APPROVED:
        log.error(
            "remediation_executor called without APPROVED status — aborting",
            status="blocked",
        )
        return {
            "status": InvestigationStatus.FAILED,
            "errors": list(state.errors) + [
                "SAFETY: remediation_executor called without approval"
            ],
        }

    log.info("Remediation executor (Phase 2 stub) — no real actions performed", status="stub")
    return {
        "status": InvestigationStatus.REMEDIATING,
        "current_step": state.current_step + 1,
    }


# ---------------------------------------------------------------------------
# Node: verification
# ---------------------------------------------------------------------------


def verification(state: AgentState) -> dict[str, Any]:
    """Verify infrastructure state after remediation.

    Phase 2: stub — returns a mock verification result.
    Phase 10+: real infrastructure state inspection.
    """
    log = _make_logger(state, "verification")
    log.info("Verification (Phase 2 stub)", status="stub")

    result = VerificationResult(
        verified=False,
        status="NOT_VERIFIED",
        details=(
            "Verification not yet implemented (Phase 10). "
            "Remediation was not executed in Phase 2."
        ),
    )
    return {
        "verification_result": result,
        "status": InvestigationStatus.VERIFYING,
        "current_step": state.current_step + 1,
    }


# ---------------------------------------------------------------------------
# Node: final_report
# ---------------------------------------------------------------------------


def final_report(state: AgentState) -> dict[str, Any]:
    """Produce the final structured incident report."""
    log = _make_logger(state, "final_report")
    log.info("Generating final report", status="started")

    remediation_actions = (
        state.remediation_plan.actions if state.remediation_plan else []
    )

    # Preserve FAILED status; anything else becomes COMPLETED
    overall = (
        InvestigationStatus.FAILED
        if state.status == InvestigationStatus.FAILED
        else InvestigationStatus.COMPLETED
    )

    report = FinalReport(
        request_id=state.request_id,
        user_request=state.user_request,
        investigation_summary=(
            f"Investigated: '{state.user_request[:100]}'. "
            f"Found {len(state.issues)} issue(s). "
            f"Root cause confidence: {state.confidence.value}."
        ),
        root_cause=state.root_cause,
        evidence_count=len(state.evidence),
        issues_found=list(state.issues),
        remediation_plan=state.remediation_plan,
        verification=state.verification_result,
        overall_status=overall,
        errors=list(state.errors),
    )

    log.info("Final report generated", status="completed")
    return {
        "final_report": report,
        "status": overall,
        "current_step": state.current_step + 1,
    }
