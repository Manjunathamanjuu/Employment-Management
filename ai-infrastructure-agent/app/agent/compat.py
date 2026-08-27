"""Runtime compatibility shims for mixed LangChain / LangGraph installs."""

from __future__ import annotations


def ensure_langchain_debug_attr() -> None:
    """langchain-core 0.3 reads ``langchain.debug`` during graph invoke.

    LangChain 1.x dropped that module attribute. Environments that still have
    both packages installed then fail every investigation with
    ``AttributeError: module 'langchain' has no attribute 'debug'``.
    """
    try:
        import langchain
    except ImportError:
        return
    if not hasattr(langchain, "debug"):
        langchain.debug = False  # type: ignore[attr-defined]
    if not hasattr(langchain, "verbose"):
        langchain.verbose = False  # type: ignore[attr-defined]
