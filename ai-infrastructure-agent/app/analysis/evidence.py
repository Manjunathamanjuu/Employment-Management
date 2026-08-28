"""Evidence collection and correlation engine.

Processes raw ToolResult objects into structured EvidenceItem records.
Separates confirmed observations from inferences.
Detects 10 incident types and correlates signals across multiple tool outputs.

Design rules:
- Evidence = observable fact from tool output
- Inference = reasoned interpretation, clearly flagged is_inference=True
- Confidence assigned per-signal, not inflated by inference
- Conflicting signals are surfaced, not silently resolved
- Missing evidence is reported explicitly
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.agent.state import ConfidenceLevel, EvidenceItem, ToolResult


# ---------------------------------------------------------------------------
# Incident pattern definitions
# ---------------------------------------------------------------------------

@dataclass
class IncidentSignal:
    """A single detected signal from a tool output."""
    incident_type: str
    observation: str
    source_tool: str
    resource: str
    confidence: ConfidenceLevel
    is_inference: bool = False
    raw_snippet: str = ""


@dataclass
class CorrelationResult:
    """Output of evidence correlation across multiple tool results."""
    evidence: list[EvidenceItem] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    incident_types: list[str] = field(default_factory=list)
    conflicting_signals: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    overall_confidence: ConfidenceLevel = ConfidenceLevel.INSUFFICIENT


# ---------------------------------------------------------------------------
# Pattern extractors — one per incident type
# ---------------------------------------------------------------------------

class CrashLoopBackOffExtractor:
    """Detects CrashLoopBackOff from pod status and events."""

    INCIDENT = "CrashLoopBackOff"

    POD_STATUS_RE = re.compile(r"CrashLoopBackOff", re.IGNORECASE)
    BACK_OFF_RE = re.compile(r"Back-?off.{0,50}restart", re.IGNORECASE)
    EXIT_CODE_RE = re.compile(r"Exit\s*Code[:\s]+(\d+)", re.IGNORECASE)
    RESTART_COUNT_RE = re.compile(r"RESTARTS\s*\n\S+\s+\S+\s+\S+\s+(\d+)", re.IGNORECASE)

    def extract(self, result: ToolResult) -> list[IncidentSignal]:
        if not result.stdout:
            return []
        signals = []
        stdout = result.stdout

        if self.POD_STATUS_RE.search(stdout):
            restart_match = self.RESTART_COUNT_RE.search(stdout)
            restart_count = restart_match.group(1) if restart_match else "unknown"
            signals.append(IncidentSignal(
                incident_type=self.INCIDENT,
                observation=f"Pod status is CrashLoopBackOff (restarts: {restart_count})",
                source_tool=result.tool_name,
                resource=result.resource or "pod",
                confidence=ConfidenceLevel.HIGH,
                raw_snippet=stdout[:300],
            ))

        if self.BACK_OFF_RE.search(stdout):
            signals.append(IncidentSignal(
                incident_type=self.INCIDENT,
                observation="Kubernetes event: Back-off restarting failed container",
                source_tool=result.tool_name,
                resource=result.resource or "pod",
                confidence=ConfidenceLevel.HIGH,
                raw_snippet=stdout[:300],
            ))

        exit_match = self.EXIT_CODE_RE.search(stdout)
        if exit_match and exit_match.group(1) != "0":
            signals.append(IncidentSignal(
                incident_type=self.INCIDENT,
                observation=f"Container terminated with exit code {exit_match.group(1)}",
                source_tool=result.tool_name,
                resource=result.resource or "pod",
                confidence=ConfidenceLevel.HIGH,
                raw_snippet=stdout[:300],
            ))

        return signals


class ImagePullBackOffExtractor:
    """Detects ImagePullBackOff / ErrImagePull from pod status and events."""

    INCIDENT = "ImagePullBackOff"

    IMAGE_PULL_RE = re.compile(
        r"(ImagePullBackOff|ErrImagePull|image.*not found|"
        r"failed to pull|unauthorized.*registry|"
        r"manifest.*unknown|no such image)",
        re.IGNORECASE,
    )
    CONTAINER_CREATING_RE = re.compile(r"ContainerCreating", re.IGNORECASE)

    def extract(self, result: ToolResult) -> list[IncidentSignal]:
        if not result.stdout:
            return []
        signals = []
        stdout = result.stdout

        if self.IMAGE_PULL_RE.search(stdout):
            match = self.IMAGE_PULL_RE.search(stdout)
            signals.append(IncidentSignal(
                incident_type=self.INCIDENT,
                observation=f"Image pull failure detected: '{match.group(0)}'",
                source_tool=result.tool_name,
                resource=result.resource or "pod",
                confidence=ConfidenceLevel.HIGH,
                raw_snippet=stdout[:300],
            ))

        return signals


class ReadinessFailureExtractor:
    """Detects readiness probe failures."""

    INCIDENT = "ReadinessFailure"

    READINESS_RE = re.compile(
        r"(Readiness probe failed|readiness probe|"
        r"READY\s+\S+\s+0/\d+|"
        r"pod\s+(?:is\s+)?not\s+ready|"
        r"unhealthy.*readiness)",
        re.IGNORECASE,
    )
    NOT_READY_RE = re.compile(r"\b0/\d+\b.*(?:Running|Pending)", re.IGNORECASE)

    def extract(self, result: ToolResult) -> list[IncidentSignal]:
        if not result.stdout:
            return []
        signals = []
        stdout = result.stdout

        if self.READINESS_RE.search(stdout):
            signals.append(IncidentSignal(
                incident_type=self.INCIDENT,
                observation="Readiness probe failure detected",
                source_tool=result.tool_name,
                resource=result.resource or "pod",
                confidence=ConfidenceLevel.HIGH,
                raw_snippet=stdout[:300],
            ))

        return signals


class LivenessFailureExtractor:
    """Detects liveness probe failures."""

    INCIDENT = "LivenessFailure"

    LIVENESS_RE = re.compile(
        r"(Liveness probe failed|liveness probe|"
        r"Killing container.*liveness|"
        r"unhealthy.*liveness|"
        r"container.*killed.*liveness)",
        re.IGNORECASE,
    )

    def extract(self, result: ToolResult) -> list[IncidentSignal]:
        if not result.stdout:
            return []
        signals = []
        if self.LIVENESS_RE.search(result.stdout):
            signals.append(IncidentSignal(
                incident_type=self.INCIDENT,
                observation="Liveness probe failure detected — container may be killed/restarted",
                source_tool=result.tool_name,
                resource=result.resource or "pod",
                confidence=ConfidenceLevel.HIGH,
                raw_snippet=result.stdout[:300],
            ))
        return signals


class ServiceNoEndpointsExtractor:
    """Detects services with no endpoints / endpoint slices."""

    INCIDENT = "ServiceNoEndpoints"

    NO_ENDPOINTS_RE = re.compile(
        r"(no endpoints|"
        r"Endpoints\s*:\s*<none>|"
        r"NotReadyAddresses\s*:\s*\d+|"
        r"Endpoints.*none|"
        r"no available endpoints)",
        re.IGNORECASE,
    )
    EMPTY_ENDPOINTS_RE = re.compile(r"ENDPOINTS\s*\n\S+\s+<none>", re.IGNORECASE)

    def extract(self, result: ToolResult) -> list[IncidentSignal]:
        if not result.stdout:
            return []
        signals = []
        stdout = result.stdout

        if self.NO_ENDPOINTS_RE.search(stdout) or self.EMPTY_ENDPOINTS_RE.search(stdout):
            signals.append(IncidentSignal(
                incident_type=self.INCIDENT,
                observation="Service has no healthy endpoints — traffic cannot be routed",
                source_tool=result.tool_name,
                resource=result.resource or "service",
                confidence=ConfidenceLevel.HIGH,
                raw_snippet=stdout[:300],
            ))
        return signals


class GatewayFailureExtractor:
    """Detects Gateway resource failures."""

    INCIDENT = "GatewayFailure"

    GATEWAY_RE = re.compile(
        r"(Programmed[:\s]+False|"
        r"Programmed.*?\n.*?False|"
        r"gateway.*not.*ready|"
        r"gateway.*error|"
        r"Accepted[:\s]+False|"
        r"GatewayClass.*not.*accepted)",
        re.IGNORECASE | re.DOTALL,
    )

    def extract(self, result: ToolResult) -> list[IncidentSignal]:
        if not result.stdout:
            return []
        signals = []
        if self.GATEWAY_RE.search(result.stdout):
            signals.append(IncidentSignal(
                incident_type=self.INCIDENT,
                observation="Gateway resource is not programmed/accepted",
                source_tool=result.tool_name,
                resource=result.resource or "gateway",
                confidence=ConfidenceLevel.HIGH,
                raw_snippet=result.stdout[:300],
            ))
        return signals


class HTTPRouteFailureExtractor:
    """Detects HTTPRoute failures."""

    INCIDENT = "HTTPRouteFailure"

    HTTPROUTE_RE = re.compile(
        r"(Accepted.*False|"
        r"ResolvedRefs.*False|"
        r"httproute.*not.*accepted|"
        r"BackendNotFound|"
        r"InvalidBackend|"
        r"route.*not.*resolved)",
        re.IGNORECASE,
    )

    def extract(self, result: ToolResult) -> list[IncidentSignal]:
        if not result.stdout:
            return []
        signals = []
        if self.HTTPROUTE_RE.search(result.stdout):
            signals.append(IncidentSignal(
                incident_type=self.INCIDENT,
                observation="HTTPRoute is not accepted or has unresolved backend references",
                source_tool=result.tool_name,
                resource=result.resource or "httproute",
                confidence=ConfidenceLevel.HIGH,
                raw_snippet=result.stdout[:300],
            ))
        return signals


class DeploymentUnavailableExtractor:
    """Detects unavailable deployments."""

    INCIDENT = "DeploymentUnavailable"

    UNAVAILABLE_RE = re.compile(
        r"(MinimumReplicasUnavailable|"
        r"DeploymentRollout.*Failed|"
        r"Unavailable\s*:\s*\d+|"
        r"ReplicaFailure|"
        r"Available\s*:\s*False|"
        # Tabular: READY column shows 0/N
        r"\b0/\d+\b(?!\s+Running|\s+CrashLoop|\s+ImagePull|\s+Pending|\s+Terminating))",
        re.IGNORECASE,
    )

    def extract(self, result: ToolResult) -> list[IncidentSignal]:
        if not result.stdout:
            return []
        signals = []
        if self.UNAVAILABLE_RE.search(result.stdout):
            signals.append(IncidentSignal(
                incident_type=self.INCIDENT,
                observation="Deployment has unavailable replicas",
                source_tool=result.tool_name,
                resource=result.resource or "deployment",
                confidence=ConfidenceLevel.HIGH,
                raw_snippet=result.stdout[:300],
            ))
        return signals


class DockerIssueExtractor:
    """Detects Docker-level issues."""

    INCIDENT = "DockerIssue"

    DOCKER_RE = re.compile(
        r"(OCI runtime.*failed|"
        r"container.*exited|"
        r"failed to start.*container|"
        r"permission denied.*docker|"
        r"Cannot connect to the Docker daemon|"
        r"error.*containerd|"
        r"image.*not.*found|"
        r"no space left on device)",
        re.IGNORECASE,
    )

    def extract(self, result: ToolResult) -> list[IncidentSignal]:
        if not result.stdout and not result.stderr:
            return []
        signals = []
        text = (result.stdout or "") + (result.stderr or "")
        if self.DOCKER_RE.search(text):
            match = self.DOCKER_RE.search(text)
            signals.append(IncidentSignal(
                incident_type=self.INCIDENT,
                observation=f"Docker/container runtime issue: '{match.group(0)[:100]}'",
                source_tool=result.tool_name,
                resource=result.resource or "container",
                confidence=ConfidenceLevel.HIGH,
                raw_snippet=text[:300],
            ))
        return signals


class TerraformIssueExtractor:
    """Detects Terraform configuration or state issues."""

    INCIDENT = "TerraformIssue"

    TF_ERROR_RE = re.compile(
        r"(Error:|error:|"
        r"configuration.*invalid|"
        r"Failed to.*provider|"
        r"terraform.*failed|"
        r"formatting.*differs|"
        r"Unsupported argument|"
        r"Missing required argument|"
        r"credential.*not found|"
        r"Plan:.*\d+\s+to\s+destroy)",
        re.IGNORECASE,
    )

    def extract(self, result: ToolResult) -> list[IncidentSignal]:
        if not result.stdout and not result.stderr:
            return []
        signals = []
        text = (result.stdout or "") + (result.stderr or "")
        if self.TF_ERROR_RE.search(text):
            match = self.TF_ERROR_RE.search(text)
            signals.append(IncidentSignal(
                incident_type=self.INCIDENT,
                observation=f"Terraform issue detected: '{match.group(0)[:100]}'",
                source_tool=result.tool_name,
                resource=result.resource or "terraform",
                confidence=ConfidenceLevel.MEDIUM,
                raw_snippet=text[:300],
            ))
        return signals


# Connection refused — cross-cutting inference trigger
class ConnRefusedExtractor:
    """Detects connection-refused errors in logs (cross-cutting)."""

    INCIDENT = "ConnectionRefused"

    CONN_RE = re.compile(
        r"(Connection refused|"
        r"connection.*timeout|"
        r"ECONNREFUSED|"
        r"failed to connect|"
        r"dial.*refused|"
        r"connect.*ETIMEDOUT)",
        re.IGNORECASE,
    )

    def extract(self, result: ToolResult) -> list[IncidentSignal]:
        if not result.stdout:
            return []
        signals = []
        if self.CONN_RE.search(result.stdout):
            match = self.CONN_RE.search(result.stdout)
            signals.append(IncidentSignal(
                incident_type=self.INCIDENT,
                observation=f"Application connectivity failure: '{match.group(0)}'",
                source_tool=result.tool_name,
                resource=result.resource or "pod",
                confidence=ConfidenceLevel.HIGH,
                raw_snippet=result.stdout[:300],
            ))
        return signals


# ---------------------------------------------------------------------------
# Evidence Collector
# ---------------------------------------------------------------------------

# All extractors
_EXTRACTORS = [
    CrashLoopBackOffExtractor(),
    ImagePullBackOffExtractor(),
    ReadinessFailureExtractor(),
    LivenessFailureExtractor(),
    ServiceNoEndpointsExtractor(),
    GatewayFailureExtractor(),
    HTTPRouteFailureExtractor(),
    DeploymentUnavailableExtractor(),
    DockerIssueExtractor(),
    TerraformIssueExtractor(),
    ConnRefusedExtractor(),
]

# Incident types that should always have supporting evidence from at least 2 tools
_HIGH_CONFIDENCE_THRESHOLD = 2


class EvidenceCollector:
    """Collects, correlates, and structures evidence from tool results.

    Usage:
        collector = EvidenceCollector()
        result = collector.collect(tool_results)
    """

    def collect(self, tool_results: list[ToolResult]) -> CorrelationResult:
        """Process all tool results and return correlated evidence."""
        all_signals: list[IncidentSignal] = []

        # Phase 1: extract raw signals
        for tool_result in tool_results:
            if tool_result.status in ("timeout", "not_found", "validation_error"):
                continue
            for extractor in _EXTRACTORS:
                signals = extractor.extract(tool_result)
                all_signals.extend(signals)

        # Phase 2: build evidence items (confirmed observations)
        evidence: list[EvidenceItem] = []
        incident_type_counts: dict[str, int] = {}

        for signal in all_signals:
            ev = EvidenceItem(
                source=signal.source_tool,
                resource=signal.resource,
                observation=signal.observation,
                confidence=signal.confidence,
                raw_reference=signal.raw_snippet[:200] if signal.raw_snippet else None,
                is_inference=signal.is_inference,
            )
            evidence.append(ev)
            if not signal.is_inference:
                incident_type_counts[signal.incident_type] = (
                    incident_type_counts.get(signal.incident_type, 0) + 1
                )

        # If tools ran but no incident signature matched, still surface the output
        # as flagged inferences so the UI is not empty. These do not raise confidence.
        if not all_signals:
            for tool_result in tool_results:
                if tool_result.status != "success":
                    continue
                snippet = (tool_result.stdout or tool_result.stderr or "").strip()
                if not snippet:
                    continue
                evidence.append(EvidenceItem(
                    source=tool_result.tool_name,
                    resource=tool_result.resource or tool_result.namespace or "cluster",
                    observation=(
                        "No incident signature matched this tool output. "
                        f"Raw result (truncated): {snippet[:300]}"
                    ),
                    confidence=ConfidenceLevel.LOW,
                    raw_reference=snippet[:200],
                    is_inference=True,
                ))

        # Phase 3: generate inferences from correlated signals
        inferences = self._generate_inferences(all_signals)
        evidence.extend(inferences)

        # Phase 4: detect conflicts
        conflicts = self._detect_conflicts(all_signals)

        # Phase 5: identify missing evidence
        missing = self._identify_missing_evidence(
            tool_results, incident_type_counts
        )

        # Phase 6: determine issues list
        issues = self._build_issues_list(incident_type_counts)

        # Phase 7: overall confidence
        overall = self._calculate_confidence(
            evidence, incident_type_counts, conflicts, tool_results
        )

        return CorrelationResult(
            evidence=evidence,
            issues=issues,
            incident_types=list(incident_type_counts.keys()),
            conflicting_signals=conflicts,
            missing_evidence=missing,
            overall_confidence=overall,
        )

    def _generate_inferences(
        self, signals: list[IncidentSignal]
    ) -> list[EvidenceItem]:
        """Create inference EvidenceItems from correlated confirmed signals."""
        inferences = []
        incident_types = {s.incident_type for s in signals if not s.is_inference}

        # CrashLoop + ConnRefused → dependency inference
        if "CrashLoopBackOff" in incident_types and "ConnectionRefused" in incident_types:
            inferences.append(EvidenceItem(
                source="evidence_correlator",
                resource="pod",
                observation=(
                    "INFERENCE: Application crash may be caused by inability to reach "
                    "a required dependency (database or service). "
                    "CrashLoopBackOff and Connection refused detected together."
                ),
                confidence=ConfidenceLevel.MEDIUM,
                is_inference=True,
            ))

        # ImagePullBackOff → registry/auth inference
        if "ImagePullBackOff" in incident_types:
            inferences.append(EvidenceItem(
                source="evidence_correlator",
                resource="pod",
                observation=(
                    "INFERENCE: Image pull failure may indicate an incorrect image tag, "
                    "a missing registry credential, or a network policy blocking "
                    "access to the container registry."
                ),
                confidence=ConfidenceLevel.MEDIUM,
                is_inference=True,
            ))

        # ServiceNoEndpoints + DeploymentUnavailable → cascade inference
        if "ServiceNoEndpoints" in incident_types and (
            "DeploymentUnavailable" in incident_types
            or "CrashLoopBackOff" in incident_types
        ):
            inferences.append(EvidenceItem(
                source="evidence_correlator",
                resource="service/deployment",
                observation=(
                    "INFERENCE: Service has no endpoints likely because the backing "
                    "pods are not ready. This is a cascading failure from the pod issue."
                ),
                confidence=ConfidenceLevel.HIGH,
                is_inference=True,
            ))

        # ReadinessFailure alone → misconfiguration inference
        if "ReadinessFailure" in incident_types and "CrashLoopBackOff" not in incident_types:
            inferences.append(EvidenceItem(
                source="evidence_correlator",
                resource="pod",
                observation=(
                    "INFERENCE: Readiness probe failure without crash may indicate "
                    "a misconfigured probe path/port or the application is slow to start."
                ),
                confidence=ConfidenceLevel.MEDIUM,
                is_inference=True,
            ))

        # GatewayFailure + HTTPRouteFailure → network path broken
        if "GatewayFailure" in incident_types and "HTTPRouteFailure" in incident_types:
            inferences.append(EvidenceItem(
                source="evidence_correlator",
                resource="gateway/httproute",
                observation=(
                    "INFERENCE: Both Gateway and HTTPRoute are unhealthy. "
                    "The complete ingress path is broken — traffic cannot reach the application."
                ),
                confidence=ConfidenceLevel.HIGH,
                is_inference=True,
            ))

        return inferences

    def _detect_conflicts(self, signals: list[IncidentSignal]) -> list[str]:
        """Detect contradictory signals that warrant explicit surfacing."""
        conflicts = []
        incident_types = {s.incident_type for s in signals if not s.is_inference}

        # Pod is both Running and CrashLoopBackOff from different tools
        running_signals = [
            s for s in signals
            if "running" in s.observation.lower() and not s.is_inference
        ]
        crash_signals = [
            s for s in signals
            if "CrashLoopBackOff" in s.observation and not s.is_inference
        ]
        if running_signals and crash_signals:
            conflicts.append(
                "Conflicting pod state: some tool results show Running while others "
                "show CrashLoopBackOff. Investigate pod lifecycle timing."
            )

        # Both readiness and liveness failures — possible probe misconfiguration
        if "ReadinessFailure" in incident_types and "LivenessFailure" in incident_types:
            conflicts.append(
                "Both readiness and liveness probes are failing. This may indicate "
                "misconfigured probe endpoints or a completely broken application."
            )

        return conflicts

    def _identify_missing_evidence(
        self,
        tool_results: list[ToolResult],
        incident_types: dict[str, int],
    ) -> list[str]:
        """Identify evidence that would improve confidence but is absent."""
        missing = []
        tool_names = {r.tool_name for r in tool_results}

        # If CrashLoop detected but no logs collected
        if "CrashLoopBackOff" in incident_types and "get_pod_logs" not in tool_names:
            missing.append(
                "Pod logs not collected — run 'get_pod_logs' to determine crash reason"
            )

        # If deployment issue but no describe_deployment
        if "DeploymentUnavailable" in incident_types and "describe_deployment" not in tool_names:
            missing.append(
                "Deployment description not collected — run 'describe_deployment' "
                "for replica set status and rollout history"
            )

        # If service issue but no endpoint slice check
        if "ServiceNoEndpoints" in incident_types and "get_endpointslices" not in tool_names:
            missing.append(
                "EndpointSlice status not checked — run 'get_endpointslices' "
                "to verify endpoint registration"
            )

        # If image pull issue but no image inspection
        if "ImagePullBackOff" in incident_types and "docker_images" not in tool_names:
            missing.append(
                "Docker image list not collected — run 'docker_images' to verify "
                "local image availability and tags"
            )

        # No tool results at all
        successful_results = [r for r in tool_results if r.status == "success"]
        if not successful_results and not incident_types:
            missing.append(
                "No successful tool results — investigation could not collect any evidence. "
                "Verify cluster connectivity and tool availability."
            )

        return missing

    def _build_issues_list(self, incident_type_counts: dict[str, int]) -> list[str]:
        """Build human-readable issues list from detected incident types."""
        issue_labels = {
            "CrashLoopBackOff": "Pod in CrashLoopBackOff",
            "ImagePullBackOff": "Image pull failure (ImagePullBackOff/ErrImagePull)",
            "ReadinessFailure": "Pod readiness probe failing",
            "LivenessFailure": "Pod liveness probe failing — container being killed",
            "ServiceNoEndpoints": "Service has no healthy endpoints",
            "GatewayFailure": "Gateway resource not programmed/accepted",
            "HTTPRouteFailure": "HTTPRoute not accepted or backend unresolved",
            "DeploymentUnavailable": "Deployment has unavailable replicas",
            "DockerIssue": "Docker/container runtime issue",
            "TerraformIssue": "Terraform configuration or state issue",
            "ConnectionRefused": "Application connectivity failure",
        }
        return [
            issue_labels.get(incident, incident)
            for incident in sorted(incident_type_counts.keys())
        ]

    def _calculate_confidence(
        self,
        evidence: list[EvidenceItem],
        incident_types: dict[str, int],
        conflicts: list[str],
        tool_results: list[ToolResult],
    ) -> ConfidenceLevel:
        """Calculate overall evidence confidence."""
        confirmed = [e for e in evidence if not e.is_inference]

        if not confirmed:
            return ConfidenceLevel.INSUFFICIENT

        high_confidence = [e for e in confirmed if e.confidence == ConfidenceLevel.HIGH]

        if not high_confidence:
            return ConfidenceLevel.LOW

        # Multiple corroborating signals across multiple tools → HIGH
        tools_with_evidence = len({
            e.source for e in confirmed if e.confidence == ConfidenceLevel.HIGH
        })

        if tools_with_evidence >= 2 and not conflicts:
            return ConfidenceLevel.HIGH

        if tools_with_evidence >= 1 and len(conflicts) <= 1:
            return ConfidenceLevel.MEDIUM

        # Conflicting or single-tool evidence
        return ConfidenceLevel.LOW
