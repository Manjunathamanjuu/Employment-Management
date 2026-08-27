"""Post-Remediation Verification Engine.

Rules:
- NEVER trust only the remediation command's exit code.
- ALWAYS inspect actual infrastructure state after remediation.
- Verification uses the same read-only tools as investigation.
- Before state is captured at plan time (from tool_results).
- After state is collected via live tool calls post-remediation.
- Status: VERIFIED, NOT_VERIFIED, PARTIALLY_VERIFIED, REMEDIATION_EXECUTED_BUT_NOT_VERIFIED
- Verification failure is reported explicitly — never silently pass.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.agent.state import (
    RemediationResult,
    VerificationResult,
)
from app.logging.logger import get_logger

logger = get_logger("ai_agent.verifier")


# ---------------------------------------------------------------------------
# Verification status constants
# ---------------------------------------------------------------------------

class VerificationStatus:
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    FAILED = "REMEDIATION_EXECUTED_BUT_NOT_VERIFIED"
    TIMEOUT = "VERIFICATION_TIMEOUT"
    UNAVAILABLE = "VERIFICATION_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Health signal extractors (reuse pattern logic from evidence module)
# ---------------------------------------------------------------------------

def _extract_pod_health(stdout: str) -> dict:
    """Extract pod health signals from kubectl get pods output."""
    if not stdout:
        return {"healthy": False, "status": "unknown", "details": "no output"}

    healthy_patterns = [
        re.compile(r"\b1/1\s+Running\b", re.IGNORECASE),
        re.compile(r"\b2/2\s+Running\b", re.IGNORECASE),
        re.compile(r"\b\d+/\d+\s+Running\b", re.IGNORECASE),
        re.compile(r"Running\s+0\s+", re.IGNORECASE),
    ]
    unhealthy_patterns = [
        re.compile(r"CrashLoopBackOff", re.IGNORECASE),
        re.compile(r"ImagePullBackOff", re.IGNORECASE),
        re.compile(r"ErrImagePull", re.IGNORECASE),
        re.compile(r"\b0/\d+\s+", re.IGNORECASE),
        re.compile(r"\bPending\b", re.IGNORECASE),
        re.compile(r"\bFailed\b", re.IGNORECASE),
        re.compile(r"\bOOMKilled\b", re.IGNORECASE),
        re.compile(r"\bTerminating\b", re.IGNORECASE),
    ]

    is_healthy = any(p.search(stdout) for p in healthy_patterns)
    is_unhealthy = any(p.search(stdout) for p in unhealthy_patterns)

    if is_healthy and not is_unhealthy:
        return {"healthy": True, "status": "Running", "details": stdout[:200]}
    if is_unhealthy:
        # Find which unhealthy pattern matched
        for p in unhealthy_patterns:
            m = p.search(stdout)
            if m:
                return {
                    "healthy": False,
                    "status": m.group(0).strip(),
                    "details": stdout[:200],
                }
    return {"healthy": False, "status": "unknown", "details": stdout[:200]}


def _extract_deployment_health(stdout: str) -> dict:
    """Extract deployment health from kubectl get/describe deployment output."""
    if not stdout:
        return {"healthy": False, "status": "unknown", "details": "no output"}

    available_pattern = re.compile(
        r"(\d+)/(\d+)\s+", re.IGNORECASE
    )
    match = available_pattern.search(stdout)
    if match:
        ready = int(match.group(1))
        desired = int(match.group(2))
        if ready == desired and ready > 0:
            return {
                "healthy": True,
                "status": f"{ready}/{desired} Ready",
                "details": stdout[:200],
            }
        return {
            "healthy": False,
            "status": f"{ready}/{desired} Ready",
            "details": stdout[:200],
        }

    if re.search(r"Available\s*:\s*True", stdout, re.IGNORECASE):
        return {"healthy": True, "status": "Available", "details": stdout[:200]}
    if re.search(r"Available\s*:\s*False", stdout, re.IGNORECASE):
        return {"healthy": False, "status": "Unavailable", "details": stdout[:200]}

    return {"healthy": False, "status": "unknown", "details": stdout[:200]}


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------

@dataclass
class VerificationSnapshot:
    """Infrastructure state at a point in time."""
    timestamp: datetime
    pod_health: dict = field(default_factory=dict)
    deployment_health: dict = field(default_factory=dict)
    raw_tool_results: list = field(default_factory=list)
    collection_errors: list = field(default_factory=list)


class Verifier:
    """Collects and compares infrastructure state before and after remediation.

    Never trusts exit codes — always reads actual infrastructure state.
    """

    def __init__(self, timeout: int = 30, namespace: str = "employment-management") -> None:
        self.timeout = timeout
        self.namespace = namespace

    def collect_state(self, request_id: str = "") -> VerificationSnapshot:
        """Collect current infrastructure state via read-only tool calls."""
        timestamp = datetime.now(timezone.utc)
        snapshot = VerificationSnapshot(timestamp=timestamp)

        # Collect pod state
        pod_result = self._run_kubectl(["kubectl", "get", "pods", "-n", self.namespace])
        snapshot.raw_tool_results.append(pod_result)
        if pod_result.get("exit_code") == 0 and pod_result.get("stdout"):
            snapshot.pod_health = _extract_pod_health(pod_result["stdout"])
        else:
            snapshot.collection_errors.append(
                f"Failed to collect pod state: {pod_result.get('error', 'unknown error')}"
            )

        # Collect deployment state
        deploy_result = self._run_kubectl(
            ["kubectl", "get", "deployments", "-n", self.namespace]
        )
        snapshot.raw_tool_results.append(deploy_result)
        if deploy_result.get("exit_code") == 0 and deploy_result.get("stdout"):
            snapshot.deployment_health = _extract_deployment_health(deploy_result["stdout"])
        else:
            snapshot.collection_errors.append(
                f"Failed to collect deployment state: {deploy_result.get('error', 'unknown')}"
            )

        return snapshot

    def verify(
        self,
        before_snapshot: Optional[VerificationSnapshot],
        remediation_results: list[RemediationResult],
        request_id: str = "",
    ) -> VerificationResult:
        """Compare before/after infrastructure state and produce a VerificationResult.

        Never trusts remediation exit codes — always inspects live state.
        """
        logger.info(
            "Starting post-remediation verification",
            extra={
                "request_id": request_id,
                "agent_node": "verification",
                "status": "started",
            },
        )

        # --- Collect after state ---
        after_snapshot = self.collect_state(request_id)

        # --- Check if collection succeeded ---
        if after_snapshot.collection_errors and not after_snapshot.pod_health:
            logger.warning(
                "Verification failed: could not collect after state",
                extra={"request_id": request_id, "agent_node": "verification",
                       "status": "failed"},
            )
            return VerificationResult(
                verified=False,
                status=VerificationStatus.FAILED,
                before_state=self._summarise_snapshot(before_snapshot),
                after_state=None,
                details=(
                    "Verification could not collect post-remediation state. "
                    f"Errors: {'; '.join(after_snapshot.collection_errors[:3])}"
                ),
            )

        # --- Compare states ---
        after_healthy = self._is_healthy(after_snapshot)
        after_state_str = self._summarise_snapshot(after_snapshot)
        before_state_str = self._summarise_snapshot(before_snapshot)

        # --- Evaluate remediation execution success ---
        executed = any(r.success for r in remediation_results) if remediation_results else False
        all_failed = all(not r.success for r in remediation_results) if remediation_results else True

        # --- Verification decision ---
        if after_healthy:
            status = VerificationStatus.VERIFIED
            verified = True
            details = (
                f"Infrastructure state is healthy after remediation. "
                f"After state: {after_state_str}"
            )
        elif not executed and not all_failed:
            status = VerificationStatus.NOT_VERIFIED
            verified = False
            details = (
                "Remediation was not fully executed. "
                "Infrastructure state unchanged from before remediation."
            )
        elif executed and not after_healthy:
            status = VerificationStatus.FAILED
            verified = False
            details = (
                f"Remediation was executed but infrastructure is still unhealthy. "
                f"Before: {before_state_str}. After: {after_state_str}. "
                "Manual investigation required."
            )
        elif not before_snapshot:
            # No before state to compare — can only report current state
            status = (
                VerificationStatus.VERIFIED if after_healthy
                else VerificationStatus.NOT_VERIFIED
            )
            verified = after_healthy
            details = f"No before state available for comparison. After: {after_state_str}"
        else:
            status = VerificationStatus.PARTIALLY_VERIFIED
            verified = False
            details = (
                f"Partial recovery: some components improved but not fully healthy. "
                f"Before: {before_state_str}. After: {after_state_str}"
            )

        logger.info(
            f"Verification complete: status={status}, verified={verified}",
            extra={
                "request_id": request_id,
                "agent_node": "verification",
                "status": status.lower() if hasattr(status, "lower") else str(status),
            },
        )

        return VerificationResult(
            verified=verified,
            status=status,
            before_state=before_state_str,
            after_state=after_state_str,
            details=details,
        )

    def verify_specific_resource(
        self,
        resource_type: str,
        resource_name: str,
        expected_status: str,
        request_id: str = "",
    ) -> VerificationResult:
        """Verify a specific named resource reached the expected status."""
        resource_type = resource_type.lower()

        if resource_type == "pod":
            result = self._run_kubectl(
                ["kubectl", "get", "pod", resource_name, "-n", self.namespace]
            )
        elif resource_type == "deployment":
            result = self._run_kubectl(
                ["kubectl", "get", "deployment", resource_name, "-n", self.namespace]
            )
        else:
            return VerificationResult(
                verified=False,
                status=VerificationStatus.UNAVAILABLE,
                details=f"Verification for resource type '{resource_type}' not supported",
            )

        if result.get("exit_code") != 0:
            return VerificationResult(
                verified=False,
                status=VerificationStatus.FAILED,
                details=(
                    f"Could not retrieve {resource_type}/{resource_name}: "
                    f"{result.get('error', 'unknown error')}"
                ),
            )

        stdout = result.get("stdout", "")
        if expected_status.lower() in stdout.lower():
            return VerificationResult(
                verified=True,
                status=VerificationStatus.VERIFIED,
                after_state=stdout[:300],
                details=(
                    f"{resource_type}/{resource_name} shows expected status "
                    f"'{expected_status}'"
                ),
            )

        return VerificationResult(
            verified=False,
            status=VerificationStatus.FAILED,
            after_state=stdout[:300],
            details=(
                f"{resource_type}/{resource_name} does NOT show expected status "
                f"'{expected_status}'. Current output: {stdout[:100]}"
            ),
        )

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _run_kubectl(self, cmd: list[str]) -> dict:
        """Run kubectl read-only command. shell=False enforced."""
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                shell=False,
            )
            return {
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "exit_code": proc.returncode,
                "error": proc.stderr if proc.returncode != 0 else None,
            }
        except subprocess.TimeoutExpired:
            logger.warning(
                f"Verification kubectl timed out: {cmd[1]}",
                extra={"agent_node": "verification", "status": "timeout"},
            )
            return {
                "stdout": None,
                "stderr": None,
                "exit_code": -1,
                "error": f"Timed out after {self.timeout}s",
            }
        except FileNotFoundError:
            return {
                "stdout": None,
                "stderr": None,
                "exit_code": -1,
                "error": "kubectl not found",
            }

    def _is_healthy(self, snapshot: Optional[VerificationSnapshot]) -> bool:
        if not snapshot:
            return False
        pod_ok = snapshot.pod_health.get("healthy", False)
        deploy_ok = snapshot.deployment_health.get("healthy", False)
        return pod_ok or deploy_ok

    def _summarise_snapshot(self, snapshot: Optional[VerificationSnapshot]) -> str:
        if not snapshot:
            return "unavailable"
        parts = []
        if snapshot.pod_health:
            parts.append(f"pods={snapshot.pod_health.get('status', 'unknown')}")
        if snapshot.deployment_health:
            parts.append(
                f"deployment={snapshot.deployment_health.get('status', 'unknown')}"
            )
        if snapshot.collection_errors:
            parts.append(f"errors={len(snapshot.collection_errors)}")
        return "; ".join(parts) if parts else "no data"
