"""Root Cause Analysis Engine.

Rules:
- Never claim HIGH confidence without multiple corroborating confirmed signals.
- Never hallucinate: if evidence is insufficient, say so explicitly.
- Separate confirmed root cause from alternative hypotheses.
- Every root cause must reference actual evidence items.
- Conflicting signals lower confidence; never silently resolve them.
- Unknown incidents are reported as UNKNOWN, not fabricated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.agent.state import (
    ConfidenceLevel,
    EvidenceItem,
    RiskLevel,
    RootCauseAnalysis,
)
from app.analysis.evidence import CorrelationResult


# ---------------------------------------------------------------------------
# Root cause templates per incident type
# ---------------------------------------------------------------------------

@dataclass
class RootCauseTemplate:
    """Template for a known incident type's root cause analysis."""
    incident_type: str
    root_cause_summary: str
    reasoning_template: str
    alternative_causes: list[str]
    recommended_next_steps: list[str]
    base_risk: RiskLevel
    # Minimum number of confirmed evidence items for HIGH confidence
    high_confidence_threshold: int = 2


_TEMPLATES: dict[str, RootCauseTemplate] = {

    "CrashLoopBackOff": RootCauseTemplate(
        incident_type="CrashLoopBackOff",
        root_cause_summary=(
            "The application container is repeatedly crashing on startup. "
            "The pod enters CrashLoopBackOff as Kubernetes backs off restart attempts."
        ),
        reasoning_template=(
            "Confirmed evidence: {evidence_summary}. "
            "The container is exiting non-zero, causing Kubernetes to restart it. "
            "The exponential back-off indicates multiple consecutive failures."
        ),
        alternative_causes=[
            "Missing or incorrect environment variable / configuration",
            "Unable to connect to a required dependency (database, service)",
            "Application bug causing immediate panic or fatal error on startup",
            "Out-of-memory kill (OOMKilled) on startup",
            "Incorrect command or entrypoint in container spec",
        ],
        recommended_next_steps=[
            "Collect full pod logs (including --previous) to identify crash reason",
            "Check environment variables and mounted secrets/configmaps",
            "Verify all dependency endpoints are reachable from the pod's network",
            "Inspect resource limits — check for OOMKilled exit code 137",
        ],
        base_risk=RiskLevel.HIGH,
        high_confidence_threshold=2,
    ),

    "CrashLoopBackOff+ConnectionRefused": RootCauseTemplate(
        incident_type="CrashLoopBackOff+ConnectionRefused",
        root_cause_summary=(
            "The application is crashing because it cannot connect to a required "
            "dependency. The 'Connection refused' error on startup causes the "
            "container to exit, triggering CrashLoopBackOff."
        ),
        reasoning_template=(
            "Confirmed evidence: {evidence_summary}. "
            "Three corroborating signals: CrashLoopBackOff pod status, "
            "'Connection refused' in application logs, and non-zero exit code. "
            "This pattern strongly indicates a dependency connectivity failure."
        ),
        alternative_causes=[
            "Incorrect hostname or port in connection configuration",
            "Target service is down or not deployed",
            "NetworkPolicy blocking egress to the dependency",
            "DNS resolution failure for the service name",
        ],
        recommended_next_steps=[
            "Verify DB_HOST / service URL environment variables are correct",
            "Check the target service is running: kubectl get pods -n <ns>",
            "Test connectivity from within the pod namespace",
            "Review NetworkPolicy resources for egress restrictions",
        ],
        base_risk=RiskLevel.HIGH,
        high_confidence_threshold=2,
    ),

    "ImagePullBackOff": RootCauseTemplate(
        incident_type="ImagePullBackOff",
        root_cause_summary=(
            "The container image cannot be pulled from the registry. "
            "The pod is stuck in ImagePullBackOff waiting for a successful image pull."
        ),
        reasoning_template=(
            "Confirmed evidence: {evidence_summary}. "
            "Kubernetes is unable to pull the specified container image. "
            "This is a definitive pre-start failure — the container never runs."
        ),
        alternative_causes=[
            "Incorrect image tag or repository URL",
            "Image tag does not exist in the registry",
            "Missing imagePullSecret for a private registry",
            "Network connectivity to the registry is blocked",
            "Registry rate-limiting (e.g. Docker Hub pull limits)",
        ],
        recommended_next_steps=[
            "Verify the image name and tag in the deployment spec",
            "Check imagePullSecrets are correctly configured",
            "Attempt to pull the image manually: docker pull <image>",
            "Review registry authentication and network policies",
        ],
        base_risk=RiskLevel.MEDIUM,
        high_confidence_threshold=1,
    ),

    "ReadinessFailure": RootCauseTemplate(
        incident_type="ReadinessFailure",
        root_cause_summary=(
            "The pod's readiness probe is failing. The pod is not receiving traffic "
            "because Kubernetes considers it not ready to serve requests."
        ),
        reasoning_template=(
            "Confirmed evidence: {evidence_summary}. "
            "The readiness probe is configured but returning a failure response. "
            "This prevents the pod from being added to service endpoint lists."
        ),
        alternative_causes=[
            "Readiness probe path or port is misconfigured",
            "Application is slow to start (initialDelaySeconds too short)",
            "Application is healthy but probe endpoint returns non-2xx",
            "Application is genuinely unhealthy and cannot serve requests",
        ],
        recommended_next_steps=[
            "Inspect the readiness probe configuration in the pod spec",
            "Test the probe endpoint manually from within the cluster",
            "Increase initialDelaySeconds or failureThreshold if app starts slowly",
            "Check application logs for errors on the health endpoint",
        ],
        base_risk=RiskLevel.MEDIUM,
        high_confidence_threshold=2,
    ),

    "LivenessFailure": RootCauseTemplate(
        incident_type="LivenessFailure",
        root_cause_summary=(
            "The pod's liveness probe is failing. Kubernetes is killing and restarting "
            "the container because it is considered unhealthy."
        ),
        reasoning_template=(
            "Confirmed evidence: {evidence_summary}. "
            "The liveness probe is consistently failing, causing Kubernetes to "
            "terminate the container. This will result in restart cycling."
        ),
        alternative_causes=[
            "Liveness probe path or port is misconfigured",
            "Application is deadlocked or stuck but not fully crashed",
            "Application is under high load causing probe timeouts",
            "Liveness probe thresholds are too aggressive",
        ],
        recommended_next_steps=[
            "Review liveness probe configuration (path, port, thresholds)",
            "Check application logs for deadlock or high-load patterns",
            "Consider increasing timeoutSeconds and failureThreshold",
            "Distinguish from readiness probe — liveness kills, readiness removes from LB",
        ],
        base_risk=RiskLevel.HIGH,
        high_confidence_threshold=2,
    ),

    "ServiceNoEndpoints": RootCauseTemplate(
        incident_type="ServiceNoEndpoints",
        root_cause_summary=(
            "The Kubernetes Service has no healthy endpoints. Traffic cannot be "
            "routed to any pod — the service selector matches no ready pods."
        ),
        reasoning_template=(
            "Confirmed evidence: {evidence_summary}. "
            "The service exists but its endpoint list is empty. "
            "This is typically caused by all backing pods being unhealthy or "
            "a label selector mismatch."
        ),
        alternative_causes=[
            "All backing pods are in CrashLoopBackOff or not ready",
            "Service selector labels do not match pod labels",
            "Pods are in a different namespace than the service",
            "No pods have been deployed for this service",
        ],
        recommended_next_steps=[
            "Verify pod labels match the service selector",
            "Check pod readiness: kubectl get pods -n <ns>",
            "Inspect endpoint slices: kubectl get endpointslices -n <ns>",
        ],
        base_risk=RiskLevel.HIGH,
        high_confidence_threshold=1,
    ),

    "GatewayFailure": RootCauseTemplate(
        incident_type="GatewayFailure",
        root_cause_summary=(
            "The Gateway resource is not programmed or accepted. "
            "The gateway controller cannot configure the underlying load balancer."
        ),
        reasoning_template=(
            "Confirmed evidence: {evidence_summary}. "
            "The Gateway status shows Programmed=False or Accepted=False. "
            "External traffic cannot reach the cluster through this gateway."
        ),
        alternative_causes=[
            "GatewayClass is not installed or misconfigured",
            "Insufficient resources to provision the load balancer",
            "Invalid Gateway configuration (listener ports, TLS config)",
            "Controller pod for the GatewayClass is not running",
        ],
        recommended_next_steps=[
            "Check GatewayClass status: kubectl get gatewayclass",
            "Inspect gateway controller pods",
            "Review Gateway conditions and events for error details",
        ],
        base_risk=RiskLevel.HIGH,
        high_confidence_threshold=1,
    ),

    "HTTPRouteFailure": RootCauseTemplate(
        incident_type="HTTPRouteFailure",
        root_cause_summary=(
            "The HTTPRoute is not accepted or has unresolved backend references. "
            "HTTP traffic cannot be routed to the application service."
        ),
        reasoning_template=(
            "Confirmed evidence: {evidence_summary}. "
            "The HTTPRoute status shows Accepted=False or ResolvedRefs=False. "
            "The route cannot be programmed because its parent gateway or "
            "backend service reference is invalid."
        ),
        alternative_causes=[
            "Backend service referenced by the route does not exist",
            "Parent Gateway is not accepting this route",
            "Namespace isolation preventing cross-namespace service reference",
            "Port mismatch between route and service",
        ],
        recommended_next_steps=[
            "Verify the backend service exists and is running",
            "Check the parentRef Gateway name and namespace",
            "Review ReferenceGrant if using cross-namespace references",
        ],
        base_risk=RiskLevel.HIGH,
        high_confidence_threshold=1,
    ),

    "DeploymentUnavailable": RootCauseTemplate(
        incident_type="DeploymentUnavailable",
        root_cause_summary=(
            "The Deployment does not have the desired number of available replicas. "
            "One or more pods are failing to reach the Ready state."
        ),
        reasoning_template=(
            "Confirmed evidence: {evidence_summary}. "
            "The deployment's available replica count is below the desired count. "
            "This typically cascades from pod-level failures."
        ),
        alternative_causes=[
            "Underlying pod failures (CrashLoopBackOff, ImagePullBackOff)",
            "Insufficient cluster resources (CPU, memory) to schedule pods",
            "Node affinity / taint-toleration issues preventing scheduling",
            "PersistentVolume not available for pods requiring storage",
        ],
        recommended_next_steps=[
            "Investigate individual pod status and events",
            "Check cluster node resource availability",
            "Review pod scheduling events for Pending pods",
        ],
        base_risk=RiskLevel.HIGH,
        high_confidence_threshold=2,
    ),

    "DockerIssue": RootCauseTemplate(
        incident_type="DockerIssue",
        root_cause_summary=(
            "A Docker or container runtime issue is preventing containers from "
            "starting or operating correctly."
        ),
        reasoning_template=(
            "Confirmed evidence: {evidence_summary}. "
            "The container runtime (Docker/containerd) is reporting errors "
            "that prevent normal container lifecycle management."
        ),
        alternative_causes=[
            "Docker daemon is not running or unreachable",
            "Insufficient disk space for container layers",
            "OCI runtime failure (runc/crun issue)",
            "Container image corruption",
        ],
        recommended_next_steps=[
            "Check Docker daemon status: systemctl status docker",
            "Check disk space: df -h",
            "Review container runtime logs",
        ],
        base_risk=RiskLevel.HIGH,
        high_confidence_threshold=1,
    ),

    "TerraformIssue": RootCauseTemplate(
        incident_type="TerraformIssue",
        root_cause_summary=(
            "A Terraform configuration or state issue was detected. "
            "Infrastructure-as-code may be out of sync or contain errors."
        ),
        reasoning_template=(
            "Confirmed evidence: {evidence_summary}. "
            "Terraform validation or plan output indicates configuration errors "
            "or planned destructive changes."
        ),
        alternative_causes=[
            "Configuration syntax error in .tf files",
            "Provider authentication failure",
            "State drift — actual infrastructure differs from state file",
            "Missing required variables or module references",
        ],
        recommended_next_steps=[
            "Run terraform validate for detailed error output",
            "Review terraform plan output for unexpected changes",
            "Check provider credentials and versions",
        ],
        base_risk=RiskLevel.MEDIUM,
        high_confidence_threshold=1,
    ),
}

# Minimum confirmed evidence count for any non-INSUFFICIENT confidence
_MIN_EVIDENCE_FOR_ANALYSIS = 1


# ---------------------------------------------------------------------------
# Root Cause Engine
# ---------------------------------------------------------------------------

class RootCauseEngine:
    """Determines the most probable root cause from correlated evidence.

    Rules enforced:
    - No HIGH confidence without >= threshold confirmed evidence items
    - No root cause claim without at least one confirmed evidence item
    - Conflicting signals always lower confidence
    - Unknown incidents return INSUFFICIENT with explicit message
    - Never invent alternative causes not in the template
    """

    def analyze(
        self,
        correlation: CorrelationResult,
        user_request: str = "",
    ) -> RootCauseAnalysis:
        """Produce a RootCauseAnalysis from a CorrelationResult."""

        confirmed = [e for e in correlation.evidence if not e.is_inference]
        incident_types = correlation.incident_types

        # --- Insufficient evidence ---
        if not confirmed or not incident_types:
            return self._insufficient_evidence(correlation, user_request)

        # --- Select primary incident type ---
        primary_type = self._select_primary_incident(incident_types, confirmed)
        template = self._get_template(primary_type, incident_types)

        # --- Build evidence summary (grounded in actual items) ---
        evidence_refs = [
            e.observation for e in confirmed[:6]
        ]
        evidence_summary = "; ".join(evidence_refs[:3]) if evidence_refs else "none"

        # --- Determine confidence ---
        confidence = self._calculate_confidence(
            template=template,
            confirmed=confirmed,
            incident_types=incident_types,
            conflicts=correlation.conflicting_signals,
        )

        # --- Build reasoning ---
        reasoning = template.reasoning_template.format(
            evidence_summary=evidence_summary
        )
        if correlation.conflicting_signals:
            reasoning += (
                f" NOTE: Conflicting signals detected: "
                f"{'; '.join(correlation.conflicting_signals[:2])}. "
                f"Confidence reduced accordingly."
            )
        if correlation.missing_evidence:
            reasoning += (
                f" NOTE: Missing evidence that could improve confidence: "
                f"{'; '.join(correlation.missing_evidence[:2])}."
            )

        # --- Determine risk ---
        risk = template.base_risk
        if confidence == ConfidenceLevel.LOW:
            # Downgrade risk when confidence is low (avoid over-reacting)
            risk = RiskLevel.MEDIUM if risk == RiskLevel.HIGH else risk

        # --- Build alternative causes (only from template — no hallucination) ---
        alternative_causes = list(template.alternative_causes)

        # Add cross-incident alternatives if multiple types detected
        if len(incident_types) > 1:
            additional = self._cross_incident_alternatives(incident_types)
            alternative_causes = list(dict.fromkeys(alternative_causes + additional))

        return RootCauseAnalysis(
            incident_status="ACTIVE",
            affected_resource=self._identify_affected_resource(confirmed),
            root_cause=template.root_cause_summary,
            confidence=confidence,
            evidence_references=evidence_refs,
            reasoning_summary=reasoning,
            alternative_causes=alternative_causes[:5],
            recommended_next_investigation=template.recommended_next_steps,
            risk=risk,
        )

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _insufficient_evidence(
        self,
        correlation: CorrelationResult,
        user_request: str,
    ) -> RootCauseAnalysis:
        """Return an explicit INSUFFICIENT evidence result — never hallucinate."""
        details = []
        if correlation.missing_evidence:
            details = correlation.missing_evidence[:3]
        else:
            details = [
                "No successful tool results were collected.",
                "Verify cluster connectivity and tool availability.",
            ]

        return RootCauseAnalysis(
            incident_status="UNKNOWN",
            affected_resource="unknown",
            root_cause=(
                "Insufficient evidence to determine root cause. "
                "No confirmed observations were collected from infrastructure tools."
            ),
            confidence=ConfidenceLevel.INSUFFICIENT,
            evidence_references=[],
            reasoning_summary=(
                "The investigation did not collect enough confirmed evidence to "
                "identify a root cause. "
                + " ".join(details)
            ),
            alternative_causes=[
                "Investigation tools unavailable (kubectl/docker/gcloud not configured)",
                "Network connectivity to cluster is broken",
                "Insufficient permissions to read cluster state",
            ],
            recommended_next_investigation=[
                "Verify kubectl is configured for the target cluster",
                "Check KUBECONFIG and cluster credentials",
                "Manually inspect pod status: kubectl get pods -n employment-management",
            ],
            risk=RiskLevel.LOW,
        )

    def _select_primary_incident(
        self,
        incident_types: list[str],
        confirmed: list[EvidenceItem],
    ) -> str:
        """Choose the most impactful incident type as the primary root cause."""
        # Priority order (most impactful / most specific first)
        priority = [
            "CrashLoopBackOff+ConnectionRefused",  # composite — most specific
            "CrashLoopBackOff",
            "ImagePullBackOff",
            "LivenessFailure",
            "ReadinessFailure",
            "DeploymentUnavailable",
            "ServiceNoEndpoints",
            "GatewayFailure",
            "HTTPRouteFailure",
            "DockerIssue",
            "TerraformIssue",
            "ConnectionRefused",
        ]

        # Check for composite CrashLoop+ConnectionRefused
        if "CrashLoopBackOff" in incident_types and "ConnectionRefused" in incident_types:
            return "CrashLoopBackOff+ConnectionRefused"

        for p in priority:
            if p in incident_types:
                return p

        # Fallback to first detected
        return incident_types[0]

    def _get_template(self, primary_type: str, all_types: list[str]) -> RootCauseTemplate:
        """Return the template for the primary incident type."""
        template = _TEMPLATES.get(primary_type)
        if template:
            return template

        # Unknown incident type — return a generic template
        return RootCauseTemplate(
            incident_type="Unknown",
            root_cause_summary=(
                f"An unrecognised incident type was detected: '{primary_type}'. "
                "The root cause cannot be determined from known patterns."
            ),
            reasoning_template=(
                "Evidence collected: {evidence_summary}. "
                "The incident does not match any known pattern. "
                "Manual investigation is required."
            ),
            alternative_causes=[
                "Novel incident type not covered by current detection patterns",
                "Multiple overlapping issues obscuring the primary cause",
            ],
            recommended_next_steps=[
                "Manually inspect all tool outputs",
                "Escalate to on-call engineer for investigation",
            ],
            base_risk=RiskLevel.MEDIUM,
            high_confidence_threshold=99,  # never HIGH for unknown
        )

    def _calculate_confidence(
        self,
        template: RootCauseTemplate,
        confirmed: list[EvidenceItem],
        incident_types: list[str],
        conflicts: list[str],
    ) -> ConfidenceLevel:
        """Calculate confidence level based on evidence quality and quantity."""
        if not confirmed:
            return ConfidenceLevel.INSUFFICIENT

        high_confirmed = [e for e in confirmed if e.confidence == ConfidenceLevel.HIGH]

        if not high_confirmed:
            return ConfidenceLevel.LOW

        # Count distinct tool sources contributing high-confidence evidence
        distinct_sources = len({e.source for e in high_confirmed})

        # Apply conflict penalty
        if len(conflicts) >= 2:
            # Multiple conflicts → cap at LOW
            return ConfidenceLevel.LOW

        # Check threshold
        if (
            len(high_confirmed) >= template.high_confidence_threshold
            and distinct_sources >= 2
            and not conflicts
        ):
            return ConfidenceLevel.HIGH

        if (
            len(high_confirmed) >= template.high_confidence_threshold
            and not conflicts
        ):
            return ConfidenceLevel.MEDIUM

        if conflicts:
            return ConfidenceLevel.LOW

        return ConfidenceLevel.MEDIUM

    def _identify_affected_resource(self, confirmed: list[EvidenceItem]) -> str:
        """Extract the most specific affected resource from evidence."""
        for e in confirmed:
            if e.resource and e.resource not in ("pod", "deployment", "service",
                                                   "gateway", "httproute", "container",
                                                   "terraform", "unknown"):
                return e.resource
        # Fall back to first resource
        for e in confirmed:
            if e.resource:
                return e.resource
        return "unknown"

    def _cross_incident_alternatives(self, incident_types: list[str]) -> list[str]:
        """Generate additional alternative causes when multiple incident types coexist."""
        extras = []
        if "ServiceNoEndpoints" in incident_types and (
            "CrashLoopBackOff" in incident_types
            or "DeploymentUnavailable" in incident_types
        ):
            extras.append(
                "Cascading failure: pod-level issue causing service endpoints to be removed"
            )
        if "GatewayFailure" in incident_types and "HTTPRouteFailure" in incident_types:
            extras.append(
                "Full ingress path broken: both gateway and route layer failures present"
            )
        return extras
