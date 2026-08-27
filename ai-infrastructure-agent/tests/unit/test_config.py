"""Unit tests for configuration loading and secret handling."""

from __future__ import annotations

import os
import importlib
import pytest

pytestmark = pytest.mark.unit


class TestSettingsDefaults:
    def test_default_app_name(self):
        from app.config import Settings
        s = Settings()
        assert "Agent" in s.app_name

    def test_default_gcp_project(self):
        from app.config import Settings
        s = Settings()
        assert s.gcp_project_id == "gcp-dev-july-2026"

    def test_default_gke_cluster(self):
        from app.config import Settings
        s = Settings()
        assert s.gke_cluster_name == "employment-management-gke"

    def test_default_namespace(self):
        from app.config import Settings
        s = Settings()
        assert s.kubernetes_namespace == "employment-management"

    def test_default_region(self):
        from app.config import Settings
        s = Settings()
        assert s.gke_region == "us-central1"

    def test_require_human_approval_default_true(self):
        from app.config import Settings
        s = Settings()
        assert s.require_human_approval is True


class TestOpenAIKeyHandling:
    def test_no_key_is_not_configured(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        from app.config import Settings
        s = Settings()
        assert not s.openai_api_key_configured

    def test_empty_key_is_not_configured(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "")
        from app.config import Settings
        s = Settings()
        assert not s.openai_api_key_configured

    def test_placeholder_key_is_not_configured(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "your-openai-api-key-here")
        from app.config import Settings
        s = Settings()
        assert not s.openai_api_key_configured

    def test_valid_key_is_configured(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder-key-for-testing")
        from app.config import Settings
        s = Settings()
        assert s.openai_api_key_configured

    def test_redacted_dict_hides_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder-key-for-testing")
        from app.config import Settings
        s = Settings()
        d = s.redacted_dict()
        assert d.get("openai_api_key") == "[REDACTED]"
        assert "sk-test" not in str(d)

    def test_redacted_dict_safe_when_no_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        from app.config import Settings
        s = Settings()
        d = s.redacted_dict()
        # Should not raise and should not expose any key
        assert "sk-" not in str(d)


class TestEnvironmentEnum:
    def test_development_valid(self):
        from app.config import Settings, Environment
        s = Settings(environment="development")
        assert s.environment == Environment.DEVELOPMENT

    def test_production_valid(self):
        from app.config import Settings, Environment
        s = Settings(environment="production")
        assert s.environment == Environment.PRODUCTION

    def test_invalid_environment_raises(self):
        from app.config import Settings
        with pytest.raises(Exception):
            Settings(environment="invalid-env")
