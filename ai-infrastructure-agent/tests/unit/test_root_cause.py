"""Unit tests for the Root Cause Analysis Engine."""

from __future__ import annotations

import pytest

from app.agent.state import ConfidenceLevel, EvidenceItem, RiskLevel, ToolResult
from app.analysis.evidence import CorrelationResult, EvidenceCollector

pytestmark = pytest.mark.unit


def _make_evidence(
    observation: str,
    source: str = "get_pods",
    resource: str = "pod/my-pod",
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    is_inference: bool = False,
) -> EvidenceItem:
    return EvidenceItem(
        source=source,
        resource=resource,
        observation=observation,
        confidence=confidence,
        is_inference=is_inference,
    )


def _make_correlation(
    evidence: list[EvidenceItem] = None,
    incident_types: list[str] = None,
    conflicts: list[str] = None,
    missing: list[str] = None,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
) -> CorrelationResult:
    return CorrelationResult(
        evidence=evidence or [],
        issues=[],
        incident_types=incident_types or [],
        conflicting_signals=conflicts or [],
        missing_evidence=missing or [],
        overall_confidence=confidence,
    )


def _analyze(correlation: CorrelationResult, request: str = "test"):
    from app.analysis.root_cause import RootCauseEngine
    return RootCauseEngine().analyze(correlation, user_request=request)


def _make_result(tool: str, stdout: str, status: str = "success") -> ToolResult:
    return ToolResult(
        tool_name=tool,
        status=status,
        command_type="read",
        stdout=stdout,
        stderr="",
    )


# ---------------------------------------------------------------------------
# Insufficient evidence
# ---------------------------------------------------------------------------

class TestInsufficientEvidence:
    def test_no_evidence_returns_insufficient(self):
        corr = _make_correlation()
        rca = _analyze(corr)
        assert rca.confidence == ConfidenceLevel.INSUFFICIENT

    def test_no_incident_types_returns_insufficient(self):
        corr = _make_correlation(
            evidence=[_make_evidence("some observation")],
            incident_types=[],
        )
        rca = _analyze(corr)
        assert rca.confidence == ConfidenceLevel.INSUFFICIENT

    def test_insufficient_says_so_explicitly(self):
        corr = _make_correlation()
        rca = _analyze(corr)
        assert "Insufficient evidence" in rca.root_cause
        assert rca.incident_status == "UNKNOWN"

    def test_insufficient_does_not_fabricate_resource(self):
        corr = _make_correlation()
        rca = _analyze(corr)
        assert rca.affected_resource == "unknown"

    def test_insufficient_still_has_next_steps(self):
        corr = _make_correlation()
        rca = _analyze(corr)
        assert len(rca.recommended_next_investigation) > 0

    def test_insufficient_risk_is_low(self):
        corr = _make_correlation()
        rca = _analyze(corr)
        assert rca.risk == RiskLevel.LOW

    def test_empty_tool_results_via_collector(self):
        from app.analysis.root_cause import RootCauseEngine
        from app.analysis.evidence import EvidenceCollector
        collector = EvidenceCollector()
        corr = collector.collect([])
        rca = RootCauseEngine().analyze(corr)
        assert rca.confidence == ConfidenceLevel.INSUFFICIENT


# ---------------------------------------------------------------------------
# HIGH confidence
# ---------------------------------------------------------------------------

class TestHighConfidence:
    def test_crashloop_plus_conn_refused_high_confidence(self):
        evidence = [
            _make_evidence("Pod status is CrashLoopBackOff (restarts: 8)", source="get_pods"),
            _make_evidence("Application log: Connection refused on startup", source="get_pod_logs"),
            _make_evidence("Container terminated with exit code 1", source="describe_pod"),
        ]
        corr = _make_correlation(
            evidence=evidence,
            incident_types=["CrashLoopBackOff", "ConnectionRefused"],
        )
        rca = _analyze(corr)
        assert rca.confidence == ConfidenceLevel.HIGH

    def test_high_confidence_has_evidence_references(self):
        evidence = [
            _make_evidence("Pod status is CrashLoopBackOff (restarts: 8)", source="get_pods"),
            _make_evidence("Application log: Connection refused on startup", source="get_pod_logs"),
        ]
        corr = _make_correlation(
            evidence=evidence,
            incident_types=["CrashLoopBackOff", "ConnectionRefused"],
        )
        rca = _analyze(corr)
        assert len(rca.evidence_references) > 0

    def test_high_confidence_root_cause_mentions_dependency(self):
        evidence = [
            _make_evidence("Pod status is CrashLoopBackOff (restarts: 5)", source="get_pods"),
            _make_evidence("Connection refused", source="get_pod_logs"),
        ]
        corr = _make_correlation(
            evidence=evidence,
            incident_types=["CrashLoopBackOff", "ConnectionRefused"],
        )
        rca = _analyze(corr)
        assert "connect" in rca.root_cause.lower() or "dependency" in rca.root_cause.lower()

    def test_high_confidence_has_alternative_causes(self):
        evidence = [
            _make_evidence("Pod status is CrashLoopBackOff (restarts: 5)", source="get_pods"),
            _make_evidence("Connection refused", source="get_pod_logs"),
        ]
        corr = _make_correlation(
            evidence=evidence,
            incident_types=["CrashLoopBackOff", "ConnectionRefused"],
        )
        rca = _analyze(corr)
        assert len(rca.alternative_causes) > 0

    def test_high_confidence_status_active(self):
        evidence = [
            _make_evidence("Pod status is CrashLoopBackOff (restarts: 5)", source="get_pods"),
            _make_evidence("Connection refused", source="get_pod_logs"),
        ]
        corr = _make_correlation(
            evidence=evidence,
            incident_types=["CrashLoopBackOff", "ConnectionRefused"],
        )
        rca = _analyze(corr)
        assert rca.incident_status == "ACTIVE"


# ---------------------------------------------------------------------------
# MEDIUM confidence
# ---------------------------------------------------------------------------

class TestMediumConfidence:
    def test_single_source_crashloop_medium_confidence(self):
        evidence = [
            _make_evidence("Pod status is CrashLoopBackOff (restarts: 3)", source="get_pods"),
        ]
        corr = _make_correlation(
            evidence=evidence,
            incident_types=["CrashLoopBackOff"],
        )
        rca = _analyze(corr)
        assert rca.confidence in (ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH)

    def test_medium_confidence_has_reasoning(self):
        evidence = [
            _make_evidence("Pod status is CrashLoopBackOff (restarts: 3)", source="get_pods"),
        ]
        corr = _make_correlation(
            evidence=evidence,
            incident_types=["CrashLoopBackOff"],
        )
        rca = _analyze(corr)
        assert rca.reasoning_summary

    def test_single_signal_image_pull_medium(self):
        evidence = [
            _make_evidence(
                "Image pull failure detected: 'ImagePullBackOff'",
                source="get_pods",
            ),
        ]
        corr = _make_correlation(
            evidence=evidence,
            incident_types=["ImagePullBackOff"],
        )
        rca = _analyze(corr)
        assert rca.confidence in (ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH)
        assert "image" in rca.root_cause.lower()


# ---------------------------------------------------------------------------
# LOW confidence
# ---------------------------------------------------------------------------

class TestLowConfidence:
    def test_conflicting_signals_lower_confidence(self):
        evidence = [
            _make_evidence("Pod status is CrashLoopBackOff", source="get_pods"),
        ]
        corr = _make_correlation(
            evidence=evidence,
            incident_types=["CrashLoopBackOff"],
            conflicts=[
                "Conflicting pod state: some tools show Running while others show CrashLoopBackOff",
                "Both readiness and liveness probes are failing simultaneously",
            ],
        )
        rca = _analyze(corr)
        assert rca.confidence == ConfidenceLevel.LOW

    def test_multiple_conflicts_cap_at_low(self):
        evidence = [
            _make_evidence("CrashLoopBackOff detected", source="get_pods"),
            _make_evidence("Readiness probe failed", source="get_events"),
        ]
        corr = _make_correlation(
            evidence=evidence,
            incident_types=["CrashLoopBackOff", "ReadinessFailure"],
            conflicts=["conflict one", "conflict two", "conflict three"],
        )
        rca = _analyze(corr)
        assert rca.confidence == ConfidenceLevel.LOW

    def test_conflict_noted_in_reasoning(self):
        evidence = [
            _make_evidence("CrashLoopBackOff", source="get_pods"),
        ]
        corr = _make_correlation(
            evidence=evidence,
            incident_types=["CrashLoopBackOff"],
            conflicts=["Running vs CrashLoopBackOff conflict"],
        )
        rca = _analyze(corr)
        # Conflicting signals should be mentioned in reasoning
        assert "conflict" in rca.reasoning_summary.lower() or "conflicting" in rca.reasoning_summary.lower()


# ---------------------------------------------------------------------------
# Hallucination resistance
# ---------------------------------------------------------------------------

class TestHallucinationResistance:
    def test_no_root_cause_without_evidence(self):
        corr = _make_correlation()
        rca = _analyze(corr)
        assert "Insufficient evidence" in rca.root_cause
        assert rca.confidence == ConfidenceLevel.INSUFFICIENT

    def test_alternative_causes_from_template_only(self):
        """Alternative causes must come from pre-defined templates, not invented."""
        from app.analysis.root_cause import _TEMPLATES
        evidence = [
            _make_evidence("Pod status is CrashLoopBackOff (restarts: 5)", source="get_pods"),
        ]
        corr = _make_correlation(
            evidence=evidence,
            incident_types=["CrashLoopBackOff"],
        )
        rca = _analyze(corr)
        template_causes = _TEMPLATES["CrashLoopBackOff"].alternative_causes
        for cause in rca.alternative_causes:
            assert cause in template_causes or "Cascading" in cause or "broken" in cause, \
                f"Alternative cause not from template: {cause!r}"

    def test_no_specific_resource_invented_when_unknown(self):
        corr = _make_correlation()
        rca = _analyze(corr)
        assert rca.affected_resource == "unknown"
        # Must not fabricate a pod name
        assert "employment-management-6d8f9b7c4" not in rca.affected_resource

    def test_insufficient_message_explicit(self):
        corr = _make_correlation()
        rca = _analyze(corr)
        assert "Insufficient" in rca.root_cause or "insufficient" in rca.root_cause

    def test_unknown_incident_type_does_not_crash(self):
        evidence = [
            _make_evidence("Some unknown incident detected", source="get_pods"),
        ]
        corr = _make_correlation(
            evidence=evidence,
            incident_types=["SomeUnknownIncidentXYZ"],
        )
        rca = _analyze(corr)
        # Should return a result, not raise
        assert rca is not None
        assert rca.confidence != ConfidenceLevel.HIGH  # Never HIGH for unknown

    def test_timeout_results_give_insufficient(self):
        results = [
            _make_result("get_pods", stdout="", status="timeout"),
            _make_result("get_events", stdout="", status="not_found"),
        ]
        from app.analysis.evidence import EvidenceCollector
        from app.analysis.root_cause import RootCauseEngine
        corr = EvidenceCollector().collect(results)
        rca = RootCauseEngine().analyze(corr)
        assert rca.confidence == ConfidenceLevel.INSUFFICIENT


# ---------------------------------------------------------------------------
# Specific incident type root causes
# ---------------------------------------------------------------------------

class TestIncidentTypeRootCauses:
    def _rca_for(self, incident_type: str, observations: list[str],
                  sources: list[str] = None) -> "RootCauseAnalysis":
        sources = sources or (["get_pods"] * len(observations))
        evidence = [
            _make_evidence(obs, source=src)
            for obs, src in zip(observations, sources)
        ]
        corr = _make_correlation(evidence=evidence, incident_types=[incident_type])
        return _analyze(corr)

    def test_imagepullbackoff_mentions_image(self):
        rca = self._rca_for(
            "ImagePullBackOff",
            ["Image pull failure detected: 'ImagePullBackOff'"],
        )
        assert "image" in rca.root_cause.lower()
        assert rca.incident_status == "ACTIVE"

    def test_readiness_failure_mentions_probe(self):
        rca = self._rca_for(
            "ReadinessFailure",
            ["Readiness probe failure detected"],
        )
        assert "readiness" in rca.root_cause.lower() or "probe" in rca.root_cause.lower()

    def test_liveness_failure_mentions_kill(self):
        rca = self._rca_for(
            "LivenessFailure",
            ["Liveness probe failure detected — container may be killed/restarted"],
        )
        assert "liveness" in rca.root_cause.lower() or "kill" in rca.root_cause.lower()

    def test_service_no_endpoints_mentions_endpoints(self):
        rca = self._rca_for(
            "ServiceNoEndpoints",
            ["Service has no healthy endpoints — traffic cannot be routed"],
        )
        assert "endpoint" in rca.root_cause.lower()

    def test_gateway_failure_mentions_gateway(self):
        rca = self._rca_for(
            "GatewayFailure",
            ["Gateway resource is not programmed/accepted"],
        )
        assert "gateway" in rca.root_cause.lower()

    def test_httproute_failure_mentions_route(self):
        rca = self._rca_for(
            "HTTPRouteFailure",
            ["HTTPRoute is not accepted or has unresolved backend references"],
        )
        assert "http" in rca.root_cause.lower() or "route" in rca.root_cause.lower()

    def test_deployment_unavailable_mentions_replicas(self):
        rca = self._rca_for(
            "DeploymentUnavailable",
            ["Deployment has unavailable replicas"],
        )
        assert "replica" in rca.root_cause.lower() or "deployment" in rca.root_cause.lower()

    def test_docker_issue_mentions_runtime(self):
        rca = self._rca_for(
            "DockerIssue",
            ["Docker/container runtime issue: 'OCI runtime create failed'"],
        )
        assert "docker" in rca.root_cause.lower() or "container" in rca.root_cause.lower()

    def test_terraform_issue_mentions_config(self):
        rca = self._rca_for(
            "TerraformIssue",
            ["Terraform issue detected: 'Error: Unsupported argument'"],
        )
        assert "terraform" in rca.root_cause.lower()


# ---------------------------------------------------------------------------
# Risk assessment
# ---------------------------------------------------------------------------

class TestRiskAssessment:
    def test_crashloop_risk_high(self):
        evidence = [
            _make_evidence("Pod status is CrashLoopBackOff (restarts: 8)", source="get_pods"),
            _make_evidence("Connection refused", source="get_pod_logs"),
        ]
        corr = _make_correlation(
            evidence=evidence,
            incident_types=["CrashLoopBackOff", "ConnectionRefused"],
        )
        rca = _analyze(corr)
        assert rca.risk in (RiskLevel.HIGH, RiskLevel.MEDIUM)

    def test_low_confidence_risk_downgraded(self):
        evidence = [
            _make_evidence("CrashLoopBackOff", source="get_pods"),
        ]
        corr = _make_correlation(
            evidence=evidence,
            incident_types=["CrashLoopBackOff"],
            conflicts=["conflict A", "conflict B"],
        )
        rca = _analyze(corr)
        assert rca.confidence == ConfidenceLevel.LOW
        # Risk should be downgraded from HIGH to MEDIUM when confidence is low
        assert rca.risk != RiskLevel.HIGH

    def test_terraform_risk_medium(self):
        evidence = [
            _make_evidence("Terraform issue: formatting error", source="terraform_fmt_check"),
        ]
        corr = _make_correlation(
            evidence=evidence,
            incident_types=["TerraformIssue"],
        )
        rca = _analyze(corr)
        assert rca.risk == RiskLevel.MEDIUM


# ---------------------------------------------------------------------------
# End-to-end via EvidenceCollector → RootCauseEngine
# ---------------------------------------------------------------------------

class TestEndToEndRootCause:
    def test_crashloop_pipeline(self):
        from app.analysis.evidence import EvidenceCollector
        from app.analysis.root_cause import RootCauseEngine
        results = [
            _make_result("get_pods", "CrashLoopBackOff Exit Code: 1 RESTARTS 5"),
            _make_result("get_events", "Back-off restarting failed container"),
        ]
        corr = EvidenceCollector().collect(results)
        rca = RootCauseEngine().analyze(corr)
        assert rca.confidence != ConfidenceLevel.INSUFFICIENT
        assert "CrashLoop" in rca.root_cause or "crash" in rca.root_cause.lower()

    def test_imagepull_pipeline(self):
        from app.analysis.evidence import EvidenceCollector
        from app.analysis.root_cause import RootCauseEngine
        results = [
            _make_result("get_pods", "ImagePullBackOff Failed to pull image"),
        ]
        corr = EvidenceCollector().collect(results)
        rca = RootCauseEngine().analyze(corr)
        assert rca.confidence != ConfidenceLevel.INSUFFICIENT
        assert "image" in rca.root_cause.lower()

    def test_empty_pipeline_insufficient(self):
        from app.analysis.evidence import EvidenceCollector
        from app.analysis.root_cause import RootCauseEngine
        corr = EvidenceCollector().collect([])
        rca = RootCauseEngine().analyze(corr)
        assert rca.confidence == ConfidenceLevel.INSUFFICIENT

    def test_multiple_incident_types_selects_primary(self):
        from app.analysis.evidence import EvidenceCollector
        from app.analysis.root_cause import RootCauseEngine
        results = [
            _make_result("get_pods", "CrashLoopBackOff"),
            _make_result("describe_service", "Endpoints: <none>"),
        ]
        corr = EvidenceCollector().collect(results)
        rca = RootCauseEngine().analyze(corr)
        # CrashLoopBackOff is higher priority than ServiceNoEndpoints
        assert "crash" in rca.root_cause.lower() or "CrashLoop" in rca.root_cause

    def test_missing_evidence_noted_in_reasoning(self):
        from app.analysis.evidence import EvidenceCollector
        from app.analysis.root_cause import RootCauseEngine
        results = [_make_result("get_pods", "CrashLoopBackOff")]
        corr = EvidenceCollector().collect(results)
        rca = RootCauseEngine().analyze(corr)
        # Missing evidence (no logs) should appear in reasoning
        assert "log" in rca.reasoning_summary.lower() or "Missing" in rca.reasoning_summary
