"""Unit tests for API Pydantic models."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestTroubleshootRequest:
    def test_valid_request(self):
        from app.api.models import TroubleshootRequest
        req = TroubleshootRequest(request="Why is my pod failing?")
        assert req.request == "Why is my pod failing?"

    def test_strips_whitespace(self):
        from app.api.models import TroubleshootRequest
        req = TroubleshootRequest(request="  test request  ")
        assert req.request == "test request"

    def test_empty_request_raises(self):
        from app.api.models import TroubleshootRequest
        with pytest.raises(Exception):
            TroubleshootRequest(request="")

    def test_blank_request_raises(self):
        from app.api.models import TroubleshootRequest
        with pytest.raises(Exception):
            TroubleshootRequest(request="   ")

    def test_too_long_request_raises(self):
        from app.api.models import TroubleshootRequest
        with pytest.raises(Exception):
            TroubleshootRequest(request="x" * 2001)

    def test_max_length_request_valid(self):
        from app.api.models import TroubleshootRequest
        req = TroubleshootRequest(request="x" * 2000)
        assert len(req.request) == 2000

    def test_valid_namespace(self):
        from app.api.models import TroubleshootRequest
        req = TroubleshootRequest(
            request="test", namespace="employment-management"
        )
        assert req.namespace == "employment-management"

    def test_invalid_namespace_with_special_chars_raises(self):
        from app.api.models import TroubleshootRequest
        with pytest.raises(Exception):
            TroubleshootRequest(request="test", namespace="ns;rm -rf /")

    def test_invalid_namespace_with_uppercase_raises(self):
        from app.api.models import TroubleshootRequest
        with pytest.raises(Exception):
            TroubleshootRequest(request="test", namespace="MyNamespace")

    def test_namespace_with_path_traversal_raises(self):
        from app.api.models import TroubleshootRequest
        with pytest.raises(Exception):
            TroubleshootRequest(request="test", namespace="../etc/passwd")

    def test_namespace_none_is_valid(self):
        from app.api.models import TroubleshootRequest
        req = TroubleshootRequest(request="test", namespace=None)
        assert req.namespace is None


class TestApprovalRequest:
    def test_valid_approval(self):
        from app.api.models import ApprovalRequest
        req = ApprovalRequest(
            request_id="req-123",
            approved=True,
            approver="ops-team",
        )
        assert req.approved is True

    def test_valid_rejection(self):
        from app.api.models import ApprovalRequest
        req = ApprovalRequest(
            request_id="req-456",
            approved=False,
            approver="security-team",
            reason="Too risky",
        )
        assert req.approved is False

    def test_empty_approver_raises(self):
        from app.api.models import ApprovalRequest
        with pytest.raises(Exception):
            ApprovalRequest(request_id="req-789", approved=True, approver="")


class TestResponseModels:
    def test_health_response_defaults(self):
        from app.api.models import HealthResponse
        resp = HealthResponse(version="1.0.0")
        assert resp.status == "ok"
        assert resp.version == "1.0.0"

    def test_ready_response(self):
        from app.api.models import ReadyResponse
        resp = ReadyResponse(ready=True, checks={"config": "ok"})
        assert resp.ready is True

    def test_error_response_no_stack_trace(self):
        from app.api.models import ErrorResponse
        resp = ErrorResponse(error="Internal error", code="INTERNAL_ERROR")
        d = resp.model_dump()
        assert "traceback" not in d
        assert "stacktrace" not in d

    def test_troubleshoot_response(self):
        from app.api.models import TroubleshootResponse
        resp = TroubleshootResponse(
            request_id="req-001",
            status="PENDING",
        )
        assert resp.request_id == "req-001"
        assert resp.evidence == []
        assert resp.remediation == []
