"""Remediation Planner.

Rules:
- NEVER execute any action — only plan and recommend.
- Every action MUST have approval_required=True.
- Every action MUST have a rollback plan.
- Dangerous actions (delete namespace, scale to 0, terraform destroy) are
  rejected and never appear in recommendations.
- Risk is calculated per action, not just per incident type.
- Confidence must be sufficient before planning — low confidence → advisory only.
- Plans are grounded in the root cause — not generic checklists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.agent.state import (
    ConfidenceLevel,
    RemediationAction,
    RemediationPlan,
    RiskLevel,
    RootCauseAnalysis,
)


# ---------------------------------------------------------------------------
# Dangerous action patterns — these are NEVER recommended
# ---------------------------------------------------------------------------

DANGEROUS_ACTIONS = frozenset({
    "kubectl delete namespace",
    "kubectl delete pvc",
    "kubectl delete persistentvolume",
    "kubectl delete clusterrole",
    "kubectl delete clusterrolebinding",
    "terraform destroy",
    "kubectl scale --replicas=0",
    "docker system prune",
    "docker rm -f",
    "gcloud projects delete",
    "gcloud container clusters delete",
    "kubectl drain",
})


def is_dangerous_action(action_description: str) -> bool:
    """Return True if an action description matches a dangerous pattern."""
    lower = action_description.lower()
    for dangerous in DANGEROUS_ACTIONS:
        if dangerous.lower() in lower:
            return True
    return False


# ---------------------------------------------------------------------------
# Remediation playbooks per incident type
# ---------------------------------------------------------------------------

@dataclass
class RemediationPlaybook:
    """Ordered list of safe remediation actions for an incident type."""
    incident_type: str
    actions: list[RemediationAction]
    overall_risk: RiskLevel = RiskLevel.MEDIUM


def _playbook_crashloop_conn_refused(namespace: str) -> RemediationPlaybook:
    return RemediationPlaybook(
        incident_type="CrashLoopBackOff+ConnectionRefused",
        overall_risk=RiskLevel.HIGH,
        actions=[
            RemediationAction(
                action=(
                    "Verify and correct the dependency connection configuration. "
                    "Check environment variables: DB_HOST, DB_PORT, DB_URL, "
                    "REDIS_URL, or equivalent service endpoint variables."
                ),
                reason=(
                    "Application log shows 'Connection refused' at startup. "
                    "The connection string or endpoint configuration is likely incorrect."
                ),
                expected_result=(
                    "Application connects to its dependency and starts successfully, "
                    "resolving the CrashLoopBackOff."
                ),
                risk=RiskLevel.LOW,
                rollback=(
                    "Revert the ConfigMap or Secret containing the connection "
                    "configuration to the previous version."
                ),
                approval_required=True,
                tool="kubectl_set_configmap",
                parameters={"namespace": namespace},
            ),
            RemediationAction(
                action=(
                    "Verify the target service/database is running and reachable "
                    "within the cluster network. Check service DNS resolution and "
                    f"pod-to-pod connectivity in namespace '{namespace}'."
                ),
                reason=(
                    "The dependency endpoint may be down or unreachable. "
                    "Network policy could be blocking egress."
                ),
                expected_result=(
                    "Connectivity confirmed or network issue identified for separate remediation."
                ),
                risk=RiskLevel.LOW,
                rollback="No state change — this is a diagnostic action only.",
                approval_required=True,
                tool="kubectl_exec_diagnostic",
                parameters={"namespace": namespace},
            ),
            RemediationAction(
                action=(
                    f"After fixing the root cause, delete the failing pod in "
                    f"namespace '{namespace}' to allow the ReplicaSet to create "
                    "a fresh replacement with the corrected configuration."
                ),
                reason=(
                    "CrashLoopBackOff back-off delay may be very long (up to 5 minutes). "
                    "Deleting the pod triggers an immediate replacement."
                ),
                expected_result=(
                    "New pod starts with the corrected configuration and transitions "
                    "to Running state."
                ),
                risk=RiskLevel.MEDIUM,
                rollback=(
                    "If the new pod also fails, roll back the Deployment to the "
                    "previous known-good revision: "
                    f"kubectl rollout undo deployment -n {namespace}"
                ),
                approval_required=True,
                tool="kubectl_delete_pod",
                parameters={"namespace": namespace},
            ),
        ],
    )


def _playbook_crashloop(namespace: str) -> RemediationPlaybook:
    return RemediationPlaybook(
        incident_type="CrashLoopBackOff",
        overall_risk=RiskLevel.HIGH,
        actions=[
            RemediationAction(
                action=(
                    "Collect full pod logs including previous container instance "
                    f"to identify the crash reason in namespace '{namespace}'."
                ),
                reason=(
                    "CrashLoopBackOff root cause is unknown without log analysis. "
                    "Logs reveal the exact error causing the exit."
                ),
                expected_result="Root cause identified from log output.",
                risk=RiskLevel.LOW,
                rollback="No state change — read-only log collection.",
                approval_required=True,
                tool="get_pod_logs",
                parameters={"namespace": namespace, "previous": True},
            ),
            RemediationAction(
                action=(
                    "Review pod resource limits and check for OOMKilled status. "
                    "Increase memory limit if the container is being killed by OOM."
                ),
                reason=(
                    "Exit code 137 indicates OOMKill. "
                    "Insufficient memory limits cause silent container kills."
                ),
                expected_result="Pod stays running after memory limit adjustment.",
                risk=RiskLevel.LOW,
                rollback="Revert resource limit change in the Deployment spec.",
                approval_required=True,
                tool="kubectl_patch_deployment",
                parameters={"namespace": namespace},
            ),
            RemediationAction(
                action=(
                    f"After identifying and fixing the root cause, delete the "
                    f"failing pod in namespace '{namespace}' to trigger immediate "
                    "replacement instead of waiting for back-off."
                ),
                reason="CrashLoopBackOff back-off can delay recovery up to 5 minutes.",
                expected_result="Fresh pod starts with the fixed configuration.",
                risk=RiskLevel.MEDIUM,
                rollback=(
                    f"kubectl rollout undo deployment -n {namespace} "
                    "to revert to previous working revision."
                ),
                approval_required=True,
                tool="kubectl_delete_pod",
                parameters={"namespace": namespace},
            ),
        ],
    )


def _playbook_imagepullbackoff(namespace: str) -> RemediationPlaybook:
    return RemediationPlaybook(
        incident_type="ImagePullBackOff",
        overall_risk=RiskLevel.MEDIUM,
        actions=[
            RemediationAction(
                action=(
                    "Verify the image name and tag in the Deployment spec. "
                    "Confirm the image exists in the registry: "
                    "us-central1-docker.pkg.dev/gcp-dev-july-2026/employment-management/."
                ),
                reason=(
                    "The most common cause is a non-existent or misspelled image tag. "
                    "Images must exist in the registry before they can be pulled."
                ),
                expected_result="Image exists with the specified tag in the registry.",
                risk=RiskLevel.LOW,
                rollback=(
                    "Update the Deployment spec to reference a known-good image tag. "
                    "kubectl rollout undo deployment can revert to previous working image."
                ),
                approval_required=True,
                tool="kubectl_patch_deployment",
                parameters={"namespace": namespace},
            ),
            RemediationAction(
                action=(
                    "Verify imagePullSecrets are configured in the Deployment spec "
                    f"and the referenced Secret exists in namespace '{namespace}'. "
                    "Confirm the Secret contains valid registry credentials."
                ),
                reason=(
                    "Private registry pulls require a Kubernetes imagePullSecret "
                    "containing valid credentials for the Artifact Registry."
                ),
                expected_result="Pod pulls image successfully with valid credentials.",
                risk=RiskLevel.LOW,
                rollback="Revert to the previous Secret value if credentials are changed.",
                approval_required=True,
                tool="kubectl_check_secret",
                parameters={"namespace": namespace},
            ),
        ],
    )


def _playbook_readiness(namespace: str) -> RemediationPlaybook:
    return RemediationPlaybook(
        incident_type="ReadinessFailure",
        overall_risk=RiskLevel.MEDIUM,
        actions=[
            RemediationAction(
                action=(
                    "Inspect the readiness probe configuration in the Deployment spec. "
                    "Verify: path, port, initialDelaySeconds, failureThreshold, periodSeconds."
                ),
                reason=(
                    "A misconfigured readiness probe (wrong path, wrong port, "
                    "or insufficient initialDelaySeconds) is the most common cause."
                ),
                expected_result=(
                    "Probe configuration corrected; pod transitions to Ready state."
                ),
                risk=RiskLevel.LOW,
                rollback="Revert probe configuration to previous values in Deployment spec.",
                approval_required=True,
                tool="kubectl_patch_deployment",
                parameters={"namespace": namespace},
            ),
            RemediationAction(
                action=(
                    "Test the readiness probe endpoint manually from within the cluster "
                    "to confirm it returns HTTP 200."
                ),
                reason=(
                    "Direct endpoint testing confirms whether the application is "
                    "actually healthy or the probe path is wrong."
                ),
                expected_result="Probe endpoint confirmed healthy or error identified.",
                risk=RiskLevel.LOW,
                rollback="No state change — diagnostic action only.",
                approval_required=True,
                tool="kubectl_exec_diagnostic",
                parameters={"namespace": namespace},
            ),
        ],
    )


def _playbook_liveness(namespace: str) -> RemediationPlaybook:
    return RemediationPlaybook(
        incident_type="LivenessFailure",
        overall_risk=RiskLevel.HIGH,
        actions=[
            RemediationAction(
                action=(
                    "Review the liveness probe configuration in the Deployment spec. "
                    "Increase timeoutSeconds and failureThreshold if the application "
                    "is under load. Verify the probe path returns HTTP 200."
                ),
                reason=(
                    "Aggressive liveness thresholds kill healthy-but-busy containers. "
                    "Liveness kills cause restarts which can cascade."
                ),
                expected_result="Container no longer killed by liveness probe.",
                risk=RiskLevel.MEDIUM,
                rollback="Revert probe thresholds to previous values.",
                approval_required=True,
                tool="kubectl_patch_deployment",
                parameters={"namespace": namespace},
            ),
        ],
    )


def _playbook_service_no_endpoints(namespace: str) -> RemediationPlaybook:
    return RemediationPlaybook(
        incident_type="ServiceNoEndpoints",
        overall_risk=RiskLevel.HIGH,
        actions=[
            RemediationAction(
                action=(
                    "Verify the Service selector labels match the pod labels exactly. "
                    f"Run: kubectl describe service -n {namespace} and compare "
                    "selector with pod labels."
                ),
                reason=(
                    "A label selector mismatch means the Service never selects any pod, "
                    "resulting in permanently empty endpoints."
                ),
                expected_result="Service selects pods and endpoints are populated.",
                risk=RiskLevel.LOW,
                rollback=(
                    "Revert Service selector or pod label changes to previous values."
                ),
                approval_required=True,
                tool="kubectl_patch_service",
                parameters={"namespace": namespace},
            ),
            RemediationAction(
                action=(
                    "Resolve the underlying pod health issue (CrashLoopBackOff / "
                    "ReadinessFailure) so that pods become Ready and are registered "
                    "as endpoints."
                ),
                reason=(
                    "If pods exist but are not Ready, the Service will have no endpoints. "
                    "Fixing the pod health automatically restores endpoints."
                ),
                expected_result="Pods become Ready; Service endpoints populated automatically.",
                risk=RiskLevel.MEDIUM,
                rollback="Revert pod configuration changes if they worsen the situation.",
                approval_required=True,
                tool="kubectl_patch_deployment",
                parameters={"namespace": namespace},
            ),
        ],
    )


def _playbook_gateway(namespace: str) -> RemediationPlaybook:
    return RemediationPlaybook(
        incident_type="GatewayFailure",
        overall_risk=RiskLevel.HIGH,
        actions=[
            RemediationAction(
                action=(
                    "Verify the GatewayClass is installed and the gateway controller "
                    "is running. Check controller pod status in the gateway controller "
                    "namespace."
                ),
                reason=(
                    "A Gateway cannot be programmed if its GatewayClass controller "
                    "is not running or the GatewayClass is not accepted."
                ),
                expected_result="GatewayClass accepted and Gateway transitions to Programmed=True.",
                risk=RiskLevel.LOW,
                rollback="No state change — diagnostic action only.",
                approval_required=True,
                tool="kubectl_describe_gateway",
                parameters={"namespace": namespace},
            ),
        ],
    )


def _playbook_httproute(namespace: str) -> RemediationPlaybook:
    return RemediationPlaybook(
        incident_type="HTTPRouteFailure",
        overall_risk=RiskLevel.HIGH,
        actions=[
            RemediationAction(
                action=(
                    "Verify the HTTPRoute backend service reference exists and is "
                    "reachable. Confirm service name, namespace, and port match "
                    "the HTTPRoute spec exactly."
                ),
                reason=(
                    "BackendNotFound or InvalidBackend status means the route "
                    "references a non-existent or unreachable service."
                ),
                expected_result="HTTPRoute transitions to Accepted=True, ResolvedRefs=True.",
                risk=RiskLevel.LOW,
                rollback="Revert HTTPRoute spec to previous backend reference.",
                approval_required=True,
                tool="kubectl_patch_httproute",
                parameters={"namespace": namespace},
            ),
        ],
    )


def _playbook_deployment_unavailable(namespace: str) -> RemediationPlaybook:
    return RemediationPlaybook(
        incident_type="DeploymentUnavailable",
        overall_risk=RiskLevel.HIGH,
        actions=[
            RemediationAction(
                action=(
                    "Investigate individual pod failures in the Deployment. "
                    "Check pod status and events to identify the specific failure mode "
                    "(CrashLoopBackOff, ImagePullBackOff, Pending, etc.)."
                ),
                reason=(
                    "Deployment unavailability is a symptom of pod-level failures. "
                    "The root cause must be addressed at the pod level."
                ),
                expected_result="Root cause of pod failure identified for targeted remediation.",
                risk=RiskLevel.LOW,
                rollback="No state change — diagnostic action only.",
                approval_required=True,
                tool="describe_pod",
                parameters={"namespace": namespace},
            ),
            RemediationAction(
                action=(
                    "If a recent rollout caused the unavailability, roll back the "
                    f"Deployment to the previous revision: "
                    f"kubectl rollout undo deployment -n {namespace}"
                ),
                reason=(
                    "A bad rollout is a common cause of deployment unavailability. "
                    "Rolling back restores the previous working configuration."
                ),
                expected_result="Deployment returns to previous working state.",
                risk=RiskLevel.MEDIUM,
                rollback=(
                    "Re-apply the rollout: kubectl rollout restart deployment "
                    f"-n {namespace}"
                ),
                approval_required=True,
                tool="kubectl_rollout_undo",
                parameters={"namespace": namespace},
            ),
        ],
    )


def _playbook_docker(namespace: str) -> RemediationPlaybook:
    return RemediationPlaybook(
        incident_type="DockerIssue",
        overall_risk=RiskLevel.HIGH,
        actions=[
            RemediationAction(
                action=(
                    "Check Docker daemon status and container runtime health on "
                    "the affected node. Review containerd/docker logs for errors."
                ),
                reason=(
                    "OCI runtime failures or daemon connectivity issues prevent "
                    "container lifecycle management."
                ),
                expected_result="Runtime error identified; daemon restarted if necessary.",
                risk=RiskLevel.MEDIUM,
                rollback="If node restart is required, cordon the node first to drain workloads.",
                approval_required=True,
                tool="docker_ps",
                parameters={},
            ),
        ],
    )


def _playbook_terraform(namespace: str) -> RemediationPlaybook:
    return RemediationPlaybook(
        incident_type="TerraformIssue",
        overall_risk=RiskLevel.MEDIUM,
        actions=[
            RemediationAction(
                action=(
                    "Run terraform validate to identify all configuration errors. "
                    "Fix each reported error in the .tf files and re-validate."
                ),
                reason=(
                    "Terraform validation errors prevent any infrastructure changes. "
                    "Fixing syntax errors unblocks the pipeline."
                ),
                expected_result="terraform validate returns success with no errors.",
                risk=RiskLevel.LOW,
                rollback="Revert .tf file changes if validation errors are introduced.",
                approval_required=True,
                tool="terraform_validate",
                parameters={},
            ),
            RemediationAction(
                action=(
                    "Review terraform plan output carefully for any unexpected "
                    "destructive changes (destroy operations). "
                    "Do NOT run terraform apply until the plan is reviewed and approved."
                ),
                reason=(
                    "A terraform plan showing destroys requires explicit human review. "
                    "Automated apply of destructive plans is strictly prohibited."
                ),
                expected_result="Plan reviewed; destructive changes understood and approved.",
                risk=RiskLevel.HIGH,
                rollback=(
                    "Do not apply. If applied accidentally, restore from state backup "
                    "or re-create resources from the Terraform configuration."
                ),
                approval_required=True,
                tool="terraform_plan",
                parameters={},
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Playbook registry
# ---------------------------------------------------------------------------

_PLAYBOOK_REGISTRY: dict[str, callable] = {
    "CrashLoopBackOff+ConnectionRefused": _playbook_crashloop_conn_refused,
    "CrashLoopBackOff":                    _playbook_crashloop,
    "ImagePullBackOff":                    _playbook_imagepullbackoff,
    "ReadinessFailure":                    _playbook_readiness,
    "LivenessFailure":                     _playbook_liveness,
    "ServiceNoEndpoints":                  _playbook_service_no_endpoints,
    "GatewayFailure":                      _playbook_gateway,
    "HTTPRouteFailure":                    _playbook_httproute,
    "DeploymentUnavailable":               _playbook_deployment_unavailable,
    "DockerIssue":                         _playbook_docker,
    "TerraformIssue":                      _playbook_terraform,
}


# ---------------------------------------------------------------------------
# Remediation Planner
# ---------------------------------------------------------------------------

class RemediationPlanner:
    """Produces a RemediationPlan grounded in root cause analysis.

    Safety guarantees:
    - approval_required=True on every action (no exceptions)
    - Dangerous actions never appear in output
    - Low confidence produces advisory-only plan (all risk=LOW)
    - No execution — plan only
    """

    def plan(
        self,
        root_cause: RootCauseAnalysis,
        namespace: str,
        confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    ) -> Optional[RemediationPlan]:
        """Generate a remediation plan from a root cause analysis.

        Returns None if confidence is INSUFFICIENT.
        Returns advisory-only plan (risk=LOW) if confidence is LOW.
        """
        if confidence == ConfidenceLevel.INSUFFICIENT:
            return None

        # Determine primary incident type from root cause
        incident_type = self._extract_incident_type(root_cause)
        playbook_fn = _PLAYBOOK_REGISTRY.get(incident_type)

        if playbook_fn is None:
            return self._generic_advisory_plan(root_cause, namespace)

        playbook = playbook_fn(namespace)

        # Filter dangerous actions (safety net — should never trigger with templates)
        safe_actions = [
            a for a in playbook.actions
            if not is_dangerous_action(a.action)
        ]

        # If confidence is LOW, downgrade all action risks to MEDIUM and add advisory flag
        if confidence == ConfidenceLevel.LOW:
            safe_actions = [
                RemediationAction(
                    remediation_id=a.remediation_id,
                    action=f"[LOW CONFIDENCE — ADVISORY ONLY] {a.action}",
                    reason=a.reason,
                    expected_result=a.expected_result,
                    risk=RiskLevel.LOW,
                    rollback=a.rollback,
                    approval_required=True,
                    tool=a.tool,
                    parameters=a.parameters,
                )
                for a in safe_actions
            ]

        # Enforce approval_required=True on all actions
        safe_actions = [
            self._enforce_approval(a) for a in safe_actions
        ]

        overall_risk = self._calculate_overall_risk(safe_actions, confidence)

        return RemediationPlan(
            actions=safe_actions,
            overall_risk=overall_risk,
            requires_approval=True,
        )

    def validate_action(self, action: RemediationAction) -> tuple[bool, str]:
        """Validate a single remediation action before it could be executed.

        Returns (is_valid, reason).
        Called by the executor in Phase 9 before any action runs.
        """
        if not action.action:
            return False, "Action description is empty"
        if not action.rollback:
            return False, "Rollback plan is missing"
        if not action.approval_required:
            return False, "approval_required must be True"
        if is_dangerous_action(action.action):
            return False, f"Action matches dangerous pattern: {action.action[:100]}"
        if not action.reason:
            return False, "Reason for action is missing"
        if not action.expected_result:
            return False, "Expected result is missing"
        return True, "valid"

    # -----------------------------------------------------------------------

    def _extract_incident_type(self, root_cause: RootCauseAnalysis) -> str:
        """Infer the primary incident type from the RootCauseAnalysis."""
        rc_lower = root_cause.root_cause.lower()
        reasoning_lower = root_cause.reasoning_summary.lower()
        combined = rc_lower + " " + reasoning_lower

        # Composite check first
        if ("crashloop" in combined or "crash" in combined) and (
            "connection refused" in combined or "connect" in combined
        ):
            return "CrashLoopBackOff+ConnectionRefused"

        priority_map = [
            ("CrashLoopBackOff",     ["crashloopbackoff", "crash loop", "crashloop"]),
            ("ImagePullBackOff",     ["imagepullbackoff", "image pull", "errimagepull"]),
            ("LivenessFailure",      ["liveness probe", "liveness"]),
            ("ReadinessFailure",     ["readiness probe", "readiness"]),
            ("ServiceNoEndpoints",   ["no healthy endpoints", "no endpoints", "endpoint"]),
            ("GatewayFailure",       ["gateway", "programmed=false", "not programmed"]),
            ("HTTPRouteFailure",     ["httproute", "http route", "backendnotfound"]),
            ("DeploymentUnavailable",["unavailable replicas", "deployment", "minimum replicas"]),
            ("DockerIssue",          ["docker", "container runtime", "oci runtime"]),
            ("TerraformIssue",       ["terraform", "infrastructure-as-code"]),
        ]

        for incident_type, keywords in priority_map:
            if any(kw in combined for kw in keywords):
                return incident_type

        return "Unknown"

    def _enforce_approval(self, action: RemediationAction) -> RemediationAction:
        """Guarantee approval_required=True regardless of input."""
        if not action.approval_required:
            return RemediationAction(
                remediation_id=action.remediation_id,
                action=action.action,
                reason=action.reason,
                expected_result=action.expected_result,
                risk=action.risk,
                rollback=action.rollback,
                approval_required=True,
                tool=action.tool,
                parameters=action.parameters,
            )
        return action

    def _calculate_overall_risk(
        self,
        actions: list[RemediationAction],
        confidence: ConfidenceLevel,
    ) -> RiskLevel:
        """Overall risk is the maximum risk across all actions."""
        if not actions:
            return RiskLevel.LOW

        risk_order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        max_risk = max(actions, key=lambda a: risk_order.index(a.risk)).risk

        # Elevate risk if confidence is low (uncertain about what we're changing)
        if confidence == ConfidenceLevel.LOW and max_risk == RiskLevel.LOW:
            return RiskLevel.MEDIUM

        return max_risk

    def _generic_advisory_plan(
        self,
        root_cause: RootCauseAnalysis,
        namespace: str,
    ) -> RemediationPlan:
        """Fallback advisory plan for unknown incident types."""
        actions = [
            RemediationAction(
                action=(
                    "Manually investigate the identified issue. "
                    "Review all collected evidence and tool outputs. "
                    "Escalate to the on-call engineer if the issue is unclear."
                ),
                reason=(
                    f"Root cause: {root_cause.root_cause[:200]}. "
                    "No automated remediation playbook is available for this incident type."
                ),
                expected_result="Issue understood and appropriate remediation identified.",
                risk=RiskLevel.LOW,
                rollback="No state change — advisory investigation only.",
                approval_required=True,
                tool=None,
                parameters={"namespace": namespace},
            )
        ]
        return RemediationPlan(
            actions=actions,
            overall_risk=RiskLevel.LOW,
            requires_approval=True,
        )
