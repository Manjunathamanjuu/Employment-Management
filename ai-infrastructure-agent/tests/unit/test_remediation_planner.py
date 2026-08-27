"""Unit tests for the Remediation Planner."""

from __future__ import annotations

import pytest

from app.agent.state import (
    ConfidenceLevel,
    RemediationAction,
    RiskLevel,
    RootCauseAnalysis,
)

pytestmark = pytest.mark.unit

NS = "employment-management"


def _make_rca(
    root_cause: str = "Pod is in CrashLoopBackOff",
    reasoning: str = "CrashLoopBackOff confirmed",
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    risk: RiskLevel = RiskLevel.HIGH,
    incident_status: str = "ACTIVE",
) -> RootCauseAnalysis:
    return RootCauseAnalysis(
        incident_status=incident_status,
        affected_resource="pod/my-pod",
        root_cause=root_cause,
        confidence=confidence,
        reasoning_summary=reasoning,
        alternative_causes=["alternative"],
        recommended_next_investigation=["next step"],
        risk=risk,
    )


def _plan(rca: RootCauseAnalysis, confidence: ConfidenceLevel = None):
    from app.analysis.remediation import RemediationPlanner
    conf = confidence or rca.confidence
    return RemediationPlanner().plan(rca, namespace=NS, confidence=conf)


# ---------------------------------------------------------------------------
# Valid remediation plans
# ---------------------------------------------------------------------------

class TestValidRemediation:
    def test_crashloop_produces_plan(self):
        rca = _make_rca(root_cause="Pod is repeatedly crashing on startup CrashLoopBackOff")
        plan = _plan(rca)
        assert plan is not None
        assert len(plan.actions) > 0

    def test_crashloop_conn_refused_produces_plan(self):
        rca = _make_rca(
            root_cause="Application crash caused by Connection refused to dependency",
            reasoning="CrashLoopBackOff and connection refused detected",
        )
        plan = _plan(rca)
        assert plan is not None
        assert len(plan.actions) >= 2

    def test_imagepullbackoff_produces_plan(self):
        rca = _make_rca(
            root_cause="Container image cannot be pulled (ImagePullBackOff)",
            reasoning="Image pull failure confirmed",
        )
        plan = _plan(rca)
        assert plan is not None
        assert len(plan.actions) > 0
        assert any("image" in a.action.lower() or "registry" in a.action.lower()
                   for a in plan.actions)

    def test_readiness_failure_produces_plan(self):
        rca = _make_rca(
            root_cause="Readiness probe is failing — pod not ready",
            reasoning="Readiness probe failure detected",
        )
        plan = _plan(rca)
        assert plan is not None
        assert any("readiness" in a.action.lower() or "probe" in a.action.lower()
                   for a in plan.actions)

    def test_liveness_failure_produces_plan(self):
        rca = _make_rca(
            root_cause="Liveness probe is failing — container being killed",
            reasoning="Liveness probe failure",
        )
        plan = _plan(rca)
        assert plan is not None
        assert any("liveness" in a.action.lower() or "probe" in a.action.lower()
                   for a in plan.actions)

    def test_service_no_endpoints_produces_plan(self):
        rca = _make_rca(
            root_cause="Service has no healthy endpoints — no endpoints available",
            reasoning="Service endpoints empty",
        )
        plan = _plan(rca)
        assert plan is not None
        assert any("selector" in a.action.lower() or "endpoint" in a.action.lower()
                   for a in plan.actions)

    def test_gateway_failure_produces_plan(self):
        rca = _make_rca(
            root_cause="Gateway not programmed — gateway controller issue",
            reasoning="Gateway Programmed=False",
        )
        plan = _plan(rca)
        assert plan is not None

    def test_httproute_failure_produces_plan(self):
        rca = _make_rca(
            root_cause="HTTPRoute not accepted — BackendNotFound",
            reasoning="HTTPRoute Accepted=False",
        )
        plan = _plan(rca)
        assert plan is not None

    def test_deployment_unavailable_produces_plan(self):
        rca = _make_rca(
            root_cause="Deployment has unavailable replicas — MinimumReplicasUnavailable",
            reasoning="Deployment unavailable replicas detected",
        )
        plan = _plan(rca)
        assert plan is not None

    def test_docker_issue_produces_plan(self):
        rca = _make_rca(
            root_cause="Docker container runtime issue — OCI runtime failed",
            reasoning="Docker daemon issue detected",
        )
        plan = _plan(rca)
        assert plan is not None

    def test_terraform_issue_produces_plan(self):
        rca = _make_rca(
            root_cause="Terraform configuration error — invalid argument",
            reasoning="Terraform validation failed",
        )
        plan = _plan(rca)
        assert plan is not None


# ---------------------------------------------------------------------------
# Approval requirement (non-negotiable)
# ---------------------------------------------------------------------------

class TestApprovalRequired:
    def test_all_actions_require_approval(self):
        rca = _make_rca(root_cause="CrashLoopBackOff detected")
        plan = _plan(rca)
        for action in plan.actions:
            assert action.approval_required is True, (
                f"Action does not require approval: {action.action[:80]}"
            )

    def test_plan_requires_approval(self):
        rca = _make_rca(root_cause="CrashLoopBackOff detected")
        plan = _plan(rca)
        assert plan.requires_approval is True

    def test_enforcement_converts_false_to_true(self):
        from app.analysis.remediation import RemediationPlanner
        planner = RemediationPlanner()
        action = RemediationAction(
            action="Test action",
            reason="Test reason",
            expected_result="Test result",
            risk=RiskLevel.LOW,
            rollback="Revert test",
            approval_required=False,  # Should be forced to True
        )
        enforced = planner._enforce_approval(action)
        assert enforced.approval_required is True

    def test_no_action_executes_without_approval_plan(self):
        """Plan must have requires_approval=True — never bypass."""
        for incident in [
            "CrashLoopBackOff detected",
            "Image pull failure ImagePullBackOff",
            "Gateway not programmed",
        ]:
            rca = _make_rca(root_cause=incident)
            plan = _plan(rca)
            if plan:
                assert plan.requires_approval is True


# ---------------------------------------------------------------------------
# Rollback requirement
# ---------------------------------------------------------------------------

class TestRollbackRequired:
    def test_every_action_has_rollback(self):
        rca = _make_rca(
            root_cause="CrashLoopBackOff crash loop connection refused dependency",
        )
        plan = _plan(rca)
        for action in plan.actions:
            assert action.rollback, (
                f"Action missing rollback: {action.action[:80]}"
            )
            assert len(action.rollback) > 10, (
                f"Rollback too short for: {action.action[:80]}"
            )

    def test_imagepull_actions_have_rollback(self):
        rca = _make_rca(root_cause="ImagePullBackOff image pull failure")
        plan = _plan(rca)
        for action in plan.actions:
            assert action.rollback

    def test_deployment_actions_have_rollback(self):
        rca = _make_rca(root_cause="Deployment unavailable replicas")
        plan = _plan(rca)
        for action in plan.actions:
            assert action.rollback


# ---------------------------------------------------------------------------
# Risk calculation
# ---------------------------------------------------------------------------

class TestRiskCalculation:
    def test_crashloop_overall_risk_medium_or_high(self):
        rca = _make_rca(root_cause="CrashLoopBackOff detected")
        plan = _plan(rca)
        assert plan.overall_risk in (RiskLevel.MEDIUM, RiskLevel.HIGH)

    def test_low_confidence_produces_low_risk_actions(self):
        rca = _make_rca(
            root_cause="CrashLoopBackOff detected",
            confidence=ConfidenceLevel.LOW,
        )
        plan = _plan(rca, confidence=ConfidenceLevel.LOW)
        assert plan is not None
        for action in plan.actions:
            assert action.risk == RiskLevel.LOW

    def test_low_confidence_labels_advisory(self):
        rca = _make_rca(
            root_cause="CrashLoopBackOff detected",
            confidence=ConfidenceLevel.LOW,
        )
        plan = _plan(rca, confidence=ConfidenceLevel.LOW)
        for action in plan.actions:
            assert "LOW CONFIDENCE" in action.action or "ADVISORY" in action.action

    def test_terraform_plan_action_is_high_risk(self):
        rca = _make_rca(root_cause="Terraform configuration issue error")
        plan = _plan(rca)
        terraform_plan_actions = [
            a for a in plan.actions
            if "plan" in a.action.lower() and "terraform" in a.action.lower()
        ]
        if terraform_plan_actions:
            assert any(a.risk == RiskLevel.HIGH for a in terraform_plan_actions)

    def test_read_only_diagnostic_is_low_risk(self):
        rca = _make_rca(root_cause="CrashLoopBackOff detected")
        plan = _plan(rca)
        diagnostic_actions = [
            a for a in plan.actions
            if "collect" in a.action.lower() or "diagnostic" in a.action.lower()
            or "review" in a.action.lower() or "verify" in a.action.lower()
        ]
        for action in diagnostic_actions:
            assert action.risk in (RiskLevel.LOW, RiskLevel.MEDIUM)


# ---------------------------------------------------------------------------
# Dangerous action blocking
# ---------------------------------------------------------------------------

class TestDangerousActionBlocked:
    DANGEROUS_INPUTS = [
        "kubectl delete namespace employment-management",
        "terraform destroy --auto-approve",
        "kubectl scale --replicas=0 deployment/my-app",
        "docker system prune -f",
        "gcloud container clusters delete my-cluster",
        "kubectl drain node --force",
    ]

    @pytest.mark.parametrize("dangerous", DANGEROUS_INPUTS)
    def test_dangerous_action_detected(self, dangerous):
        from app.analysis.remediation import is_dangerous_action
        assert is_dangerous_action(dangerous), (
            f"Dangerous action not detected: {dangerous}"
        )

    def test_safe_action_not_flagged(self):
        from app.analysis.remediation import is_dangerous_action
        assert not is_dangerous_action("kubectl get pods -n employment-management")
        assert not is_dangerous_action("Verify readiness probe configuration")
        assert not is_dangerous_action("Review connection string environment variable")

    def test_dangerous_action_never_in_plan(self):
        from app.analysis.remediation import is_dangerous_action
        for incident in ["CrashLoopBackOff", "ImagePullBackOff", "Deployment unavailable replicas"]:
            rca = _make_rca(root_cause=incident)
            plan = _plan(rca)
            if plan:
                for action in plan.actions:
                    assert not is_dangerous_action(action.action), (
                        f"Dangerous action in plan: {action.action[:100]}"
                    )


# ---------------------------------------------------------------------------
# INSUFFICIENT confidence → no plan
# ---------------------------------------------------------------------------

class TestInsufficientConfidence:
    def test_insufficient_confidence_returns_none(self):
        rca = _make_rca(
            root_cause="Insufficient evidence to determine root cause",
            confidence=ConfidenceLevel.INSUFFICIENT,
        )
        plan = _plan(rca, confidence=ConfidenceLevel.INSUFFICIENT)
        assert plan is None

    def test_node_skips_with_insufficient_confidence(self):
        from app.agent.nodes import remediation_planner
        from app.agent.state import AgentState, ApprovalStatus, InvestigationStatus
        state = AgentState(
            user_request="test",
            confidence=ConfidenceLevel.INSUFFICIENT,
            approval_status=ApprovalStatus.PENDING,
        )
        result = remediation_planner(state)
        assert result["status"] == InvestigationStatus.REMEDIATION_PLANNED
        assert result.get("remediation_plan") is None


# ---------------------------------------------------------------------------
# Action validation
# ---------------------------------------------------------------------------

class TestActionValidation:
    def _make_action(self, **overrides) -> RemediationAction:
        defaults = dict(
            action="Update readiness probe configuration",
            reason="Probe is misconfigured",
            expected_result="Pod transitions to Ready",
            risk=RiskLevel.MEDIUM,
            rollback="Revert probe configuration",
            approval_required=True,
        )
        defaults.update(overrides)
        return RemediationAction(**defaults)

    def test_valid_action(self):
        from app.analysis.remediation import RemediationPlanner
        action = self._make_action()
        valid, reason = RemediationPlanner().validate_action(action)
        assert valid is True

    def test_empty_action_invalid(self):
        from app.analysis.remediation import RemediationPlanner
        action = self._make_action(action="")
        valid, reason = RemediationPlanner().validate_action(action)
        assert valid is False
        assert "empty" in reason.lower()

    def test_missing_rollback_invalid(self):
        from app.analysis.remediation import RemediationPlanner
        action = self._make_action(rollback="")
        valid, reason = RemediationPlanner().validate_action(action)
        assert valid is False
        assert "rollback" in reason.lower()

    def test_approval_false_invalid(self):
        from app.analysis.remediation import RemediationPlanner
        action = self._make_action(approval_required=False)
        valid, reason = RemediationPlanner().validate_action(action)
        assert valid is False
        assert "approval" in reason.lower()

    def test_dangerous_action_invalid(self):
        from app.analysis.remediation import RemediationPlanner
        action = self._make_action(action="kubectl delete namespace employment-management")
        valid, reason = RemediationPlanner().validate_action(action)
        assert valid is False
        assert "dangerous" in reason.lower()

    def test_missing_reason_invalid(self):
        from app.analysis.remediation import RemediationPlanner
        action = self._make_action(reason="")
        valid, reason_msg = RemediationPlanner().validate_action(action)
        assert valid is False

    def test_missing_expected_result_invalid(self):
        from app.analysis.remediation import RemediationPlanner
        action = self._make_action(expected_result="")
        valid, reason_msg = RemediationPlanner().validate_action(action)
        assert valid is False


# ---------------------------------------------------------------------------
# Remediation IDs
# ---------------------------------------------------------------------------

class TestRemediationIds:
    def test_each_action_has_unique_id(self):
        rca = _make_rca(
            root_cause="CrashLoopBackOff crash loop connection refused",
        )
        plan = _plan(rca)
        ids = [a.remediation_id for a in plan.actions]
        assert len(ids) == len(set(ids)), "Duplicate remediation IDs found"

    def test_ids_are_valid_uuids(self):
        import uuid
        rca = _make_rca(root_cause="CrashLoopBackOff detected")
        plan = _plan(rca)
        for action in plan.actions:
            uuid.UUID(action.remediation_id)  # raises if invalid
