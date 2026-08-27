"""Shared pytest fixtures."""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def clear_env_secrets(monkeypatch):
    """Ensure no real secrets leak between tests."""
    # Remove any real key that might be in the shell environment
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.fixture
def client_without_key():
    """TestClient with NO OpenAI key configured."""
    os.environ.pop("OPENAI_API_KEY", None)
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client_with_key(monkeypatch):
    """TestClient with a dummy (non-real) OpenAI key configured."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder-key-for-testing-only")
    # Re-import settings to pick up the env var
    import importlib
    import app.config as cfg_module
    cfg_module.settings = cfg_module.Settings()
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)
