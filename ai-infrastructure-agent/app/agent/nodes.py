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

        if tool_name in KUBERNETES_TOOLS:
            try:
                tool = get_kubernetes_tool(tool_name, timeout=settings.tool_timeout_seconds)
                result = tool.execute(**step.parameters)
            except (ValueError, TypeError) as exc:
                result = ToolResult(
                    tool_name=tool_name,
                    status="validation_error",
                    command_type="read",
                    error=str(exc),
                    namespace=step.parameters.get("namespace"),
                )
        else:
            # Phase 2 mock fallback for tools not yet implemented
            result = _mock_tool_result(tool_name, step.parameters)

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
    """Extract structured evidence from tool results.

    Separates confirmed observations from inferences.
    Phase 2: rule-based extraction.
    Phase 5+: LLM-assisted correlation.
    """
    log = _make_logger(state, "evidence_analyzer")
    log.info("Analyzing evidence", status="started")

    evidence: list[EvidenceItem] = list(state.evidence)
    issues: list[str] = list(state.issues)

    for result in state.tool_results:
        if not result.stdout:
            continue

        stdout = result.stdout

        # CrashLoopBackOff — confirmed observation
        if "CrashLoopBackOff" in stdout:
            evidence.append(
                EvidenceItem(
                    source=result.tool_name,
                    resource="pod/employment-management-6d8f9b7c4-xkp2n",
                    observation="Pod is in CrashLoopBackOff state",
                    confidence=ConfidenceLevel.HIGH,
                    raw_reference=stdout[:200],
                    is_inference=False,
                )
            )
            if "Pod in CrashLoopBackOff" not in issues:
                issues.append("Pod in CrashLoopBackOff")

        # Connection refused — confirmed log observation
        if "Connection refused" in stdout:
            evidence.append(
                EvidenceItem(
                    source=result.tool_name,
                    resource="pod/employment-management-6d8f9b7c4-xkp2n",
                    observation="Application log: Connection refused on startup",
                    confidence=ConfidenceLevel.HIGH,
                    raw_reference=stdout[:200],
                    is_inference=False,
                )
            )
            # Inference: likely cannot reach a dependency
            evidence.append(
                EvidenceItem(
                    source="evidence_analyzer",
                    resource="pod/employment-management-6d8f9b7c4-xkp2n",
                    observation=(
                        "Application may be unable to reach a required dependency "
                        "(database or external service)"
                    ),
                    confidence=ConfidenceLevel.MEDIUM,
                    is_inference=True,
                )
            )
            if "Application startup failure" not in issues:
                issues.append("Application startup failure")

        # Exit code 1
        if "Exit Code: 1" in stdout or "Exiting with code 1" in stdout:
            evidence.append(
                EvidenceItem(
                    source=result.tool_name,
                    resource="pod/employment-management-6d8f9b7c4-xkp2n",
                    observation="Container exiting with code 1 (application error)",
                    confidence=ConfidenceLevel.HIGH,
                    raw_reference=stdout[:200],
                    is_inference=False,
                )
            )

        # BackOff event
        if "BackOff" in stdout and result.tool_name == "get_events":
            evidence.append(
                EvidenceItem(
                    source=result.tool_name,
                    resource="pod/employment-management-6d8f9b7c4-xkp2n",
                    observation="Kubernetes event: Back-off restarting failed container",
                    confidence=ConfidenceLevel.HIGH,
                    raw_reference=stdout[:200],
                    is_inference=False,
                )
            )

    log.info(
        f"Evidence analysis complete: {len(evidence)} items, {len(issues)} issues",
        status="completed",
    )
    return {
        "evidence": evidence,
        "issues": issues,
        "current_step": state.current_step + 1,
    }


# ---------------------------------------------------------------------------
# Node: root_cause_analyzer
# ---------------------------------------------------------------------------


def root_cause_analyzer(state: AgentState) -> dict[str, Any]:
    """Determine probable root cause from collected evidence.

    Assigns confidence only when evidence supports it.
    Never hallucinates — explicitly flags insufficient evidence.
    Phase 2: rule-based analysis.
    Phase 6+: LLM-assisted with evidence grounding.
    """
    log = _make_logger(state, "root_cause_analyzer")
    log.info("Running root cause analysis", status="started")

    confirmed = [e for e in state.evidence if not e.is_inference]
    inferred = [e for e in state.evidence if e.is_inference]

    if not confirmed:
        rca = RootCauseAnalysis(
            incident_status="UNKNOWN",
            affected_resource="unknown",
            root_cause="Insufficient evidence to determine root cause",
            confidence=ConfidenceLevel.INSUFFICIENT,
            reasoning_summary=(
                "No confirmed evidence was collected. "
                "Cannot determine root cause without observable facts."
            ),
            recommended_next_investigation=[
                "Verify kubectl access to the cluster",
                "Check pod status manually",
            ],
            risk=RiskLevel.LOW,
        )
        log.warning("Insufficient evidence for root cause", status="completed")
        return {
            "root_cause": rca,
            "confidence": ConfidenceLevel.INSUFFICIENT,
            "status": InvestigationStatus.ANALYZED,
            "current_step": state.current_step + 1,
        }

    # Determine confidence based on evidence count and consistency
    crash_loop = any("CrashLoopBackOff" in e.observation for e in confirmed)
    conn_refused = any("Connection refused" in e.observation for e in confirmed)
    exit_code_1 = any("exit" in e.observation.lower() and "1" in e.observation for e in confirmed)

    evidence_refs = [e.observation for e in confirmed[:5]]

    if crash_loop and conn_refused and exit_code_1:
        confidence = ConfidenceLevel.HIGH
        root_cause = (
            "Application is failing to start due to an inability to connect to a "
            "required dependency (likely the database or a backend service). "
            "This causes the container to exit with code 1, triggering CrashLoopBackOff."
        )
        reasoning = (
            "Three corroborating signals: "
            "(1) Pod status shows CrashLoopBackOff, "
            "(2) application logs show 'Connection refused' at startup, "
            "(3) container exit code is 1. "
            "All evidence is consistent with a dependency connectivity failure."
        )
        alternative_causes = [
            "Missing environment variable or misconfigured connection string",
            "Target service is down or not reachable from this namespace",
            "Network policy blocking egress to the dependency",
        ]
        next_steps = [
            "Verify database/service endpoint is reachable from the pod's network",
            "Check environment variables for connection configuration",
            "Inspect NetworkPolicy resources in the namespace",
        ]
        risk = RiskLevel.MEDIUM

    elif crash_loop:
        confidence = ConfidenceLevel.MEDIUM
        root_cause = (
            "Pod is in CrashLoopBackOff. The application is repeatedly crashing on startup. "
            "The precise cause requires additional log analysis."
        )
        reasoning = (
            "CrashLoopBackOff confirmed via pod status. "
            "Log evidence is partial — full root cause requires deeper investigation."
        )
        alternative_causes = [
            "Application configuration error",
            "Missing dependency",
            "OOM kill",
        ]
        next_steps = ["Collect full container logs", "Inspect resource limits"]
        risk = RiskLevel.MEDIUM

    else:
        confidence = ConfidenceLevel.LOW
        root_cause = "Evidence collected but root cause is unclear. Further investigation required."
        reasoning = "Collected evidence does not point to a single clear root cause."
        alternative_causes = []
        next_steps = ["Collect more diagnostic data"]
        risk = RiskLevel.LOW

    rca = RootCauseAnalysis(
        incident_status="ACTIVE",
        affected_resource="pod/employment-management-6d8f9b7c4-xkp2n",
        root_cause=root_cause,
        confidence=confidence,
        evidence_references=evidence_refs,
        reasoning_summary=reasoning,
        alternative_causes=alternative_causes,
        recommended_next_investigation=next_steps,
        risk=risk,
    )

    log.info(
        f"Root cause identified with {confidence.value} confidence",
        status="completed",
    )
    return {
        "root_cause": rca,
        "confidence": confidence,
        "risk": risk,
        "status": InvestigationStatus.ANALYZED,
        "current_step": state.current_step + 1,
    }


# ---------------------------------------------------------------------------
# Node: remediation_planner
# ---------------------------------------------------------------------------


def remediation_planner(state: AgentState) -> dict[str, Any]:
    """Generate remediation recommendations — does NOT execute anything.

    Every action requires explicit human approval before execution.
    Phase 2: deterministic recommendations.
    Phase 7+: LLM-generated with risk scoring.
    """
    log = _make_logger(state, "remediation_planner")
    log.info("Planning remediation", status="started")

    if not state.root_cause or state.confidence == ConfidenceLevel.INSUFFICIENT:
        log.warning("Skipping remediation planning — insufficient confidence", status="skipped")
        return {
            "status": InvestigationStatus.REMEDIATION_PLANNED,
            "current_step": state.current_step + 1,
        }

    actions: list[RemediationAction] = []

    rca = state.root_cause
    conn_refused = any(
        "Connection refused" in e.observation for e in state.evidence if not e.is_inference
    )
    crash_loop = any(
        "CrashLoopBackOff" in e.observation for e in state.evidence if not e.is_inference
    )

    if conn_refused:
        actions.append(
            RemediationAction(
                action=(
                    "Verify and correct the database/service connection configuration. "
                    "Check environment variables: DB_HOST, DB_PORT, DB_URL, or equivalent."
                ),
                reason=(
                    "Application log shows 'Connection refused' at startup, "
                    "indicating a misconfigured or unreachable dependency endpoint."
                ),
                expected_result=(
                    "Application connects successfully to the dependency and starts normally."
                ),
                risk=RiskLevel.LOW,
                rollback="Revert environment variable changes to previous values.",
                approval_required=True,
                tool="kubectl_set_env",
                parameters={"namespace": settings.kubernetes_namespace},
            )
        )

    if crash_loop:
        actions.append(
            RemediationAction(
                action=(
                    "After resolving the root cause, delete the failing pod to allow "
                    "the ReplicaSet to create a fresh replacement."
                ),
                reason=(
                    "CrashLoopBackOff prevents the pod from recovering automatically "
                    "once the underlying issue is fixed."
                ),
                expected_result="New pod starts successfully without CrashLoopBackOff.",
                risk=RiskLevel.MEDIUM,
                rollback=(
                    "If new pod also fails, roll back the Deployment to the "
                    "previous known-good revision."
                ),
                approval_required=True,
                tool="kubectl_delete_pod",
                parameters={
                    "namespace": settings.kubernetes_namespace,
                    "pod": "employment-management-6d8f9b7c4-xkp2n",
                },
            )
        )

    overall_risk = (
        RiskLevel.MEDIUM
        if any(a.risk == RiskLevel.MEDIUM for a in actions)
        else RiskLevel.LOW
    )

    plan = RemediationPlan(
        actions=actions,
        overall_risk=overall_risk,
        requires_approval=True,
    )

    log.info(
        f"Remediation plan created: {len(actions)} actions, risk={overall_risk.value}",
        status="completed",
    )
    return {
        "remediation_plan": plan,
        "risk": overall_risk,
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
