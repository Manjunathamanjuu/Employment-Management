"""Shared pytest fixtures."""

from __future__ import annotations

import os

# Force-disable tracing. setdefault is not enough if the shell already
# exported LANGCHAIN_TRACING_V2=true — graph.invoke then leaves LangSmith
# background work that deadlocks FastAPI TestClient on Windows.
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_CALLBACKS_BACKGROUND"] = "false"

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def clear_env_secrets(monkeypatch):
    """Ensure no real secrets leak between tests and settings are reset."""
    # Remove any real key that might be in the shell environment
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    yield
    # Reset settings singleton after each test to prevent state contamination
    import app.config as cfg_module
    cfg_module.settings = cfg_module.Settings()
    import app.api.routes as routes_module
    routes_module.settings = cfg_module.settings
    import app.main as main_module
    main_module.settings = cfg_module.settings
    from app.security import get_rate_limiter
    get_rate_limiter().reset()
    import app.agent.graph as graph_module
    graph_module._compiled_graph = None


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
