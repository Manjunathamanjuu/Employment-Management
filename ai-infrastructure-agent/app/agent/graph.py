"""LangGraph workflow definition.

LangGraph 1.x StateGraph(dict) passes the previous node's return value directly
to the next node rather than accumulating state. Each node wrapper therefore
receives the full state dict as input, merges the typed-node's partial result
into it, and returns the complete updated dict.

Workflow:
  request_analyzer → investigation_planner → tool_executor
    → evidence_analyzer → root_cause_analyzer → remediation_planner
    → approval_gate → [remediation_executor | final_report]
    → verification → final_report
"""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    approval_gate,
    evidence_analyzer,
    final_report,
    investigation_planner,
    remediation_executor,
    remediation_planner,
    request_analyzer,
    root_cause_analyzer,
    tool_executor,
    verification,
)
from app.agent.state import AgentState, InvestigationStatus
from app.logging.logger import get_logger

logger = get_logger("ai_agent.graph")


# ---------------------------------------------------------------------------
# State serialisation helpers
# ---------------------------------------------------------------------------


def _to_state(d: dict) -> AgentState:
    """Deserialise a raw dict to a typed AgentState."""
    return AgentState.model_validate(d)


def _serialise(obj: Any) -> Any:
    """Recursively convert Pydantic models → JSON-compatible dicts."""
    from pydantic import BaseModel
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [_serialise(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _serialise(v) for k, v in obj.items()}
    # Enums, datetimes, etc. are handled by model_dump(mode="json") above;
    # anything that reaches here is a plain Python value.
    return obj


def _node_wrapper(node_fn):
    """Wrap a typed-AgentState node for LangGraph 1.x.

    Each wrapper:
    1. Receives the full state dict (forwarded from the previous wrapper).
    2. Deserialises it to AgentState for type-safe node access.
    3. Runs the node, which returns a PARTIAL update dict.
    4. Deep-merges the update into a copy of the full state dict.
    5. Returns the complete merged dict so the next node sees full state.
    """
    def wrapper(state_dict: dict) -> dict:
        state = _to_state(state_dict)
        partial = node_fn(state)
        # Merge partial updates into the full serialised state
        full = dict(state_dict)
        for k, v in _serialise(partial).items():
            full[k] = v
        return full

    wrapper.__name__ = node_fn.__name__
    return wrapper


# ---------------------------------------------------------------------------
# Conditional routing (operate on full state dicts)
# ---------------------------------------------------------------------------


def _route_after_request_analyzer(
    state_dict: dict,
) -> Literal["investigation_planner", "final_report"]:
    state = _to_state(state_dict)
    if state.status == InvestigationStatus.FAILED:
        return "final_report"
    return "investigation_planner"


def _route_after_approval_gate(
    state_dict: dict,
) -> Literal["remediation_executor", "final_report"]:
    state = _to_state(state_dict)
    if state.status == InvestigationStatus.REMEDIATION_APPROVED:
        return "remediation_executor"
    return "final_report"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_graph():
    """Construct and compile the LangGraph StateGraph."""
    graph = StateGraph(dict)

    graph.add_node("request_analyzer", _node_wrapper(request_analyzer))
    graph.add_node("investigation_planner", _node_wrapper(investigation_planner))
    graph.add_node("tool_executor", _node_wrapper(tool_executor))
    graph.add_node("evidence_analyzer", _node_wrapper(evidence_analyzer))
    graph.add_node("root_cause_analyzer", _node_wrapper(root_cause_analyzer))
    graph.add_node("remediation_planner", _node_wrapper(remediation_planner))
    graph.add_node("approval_gate", _node_wrapper(approval_gate))
    graph.add_node("remediation_executor", _node_wrapper(remediation_executor))
    graph.add_node("verification", _node_wrapper(verification))
    graph.add_node("final_report", _node_wrapper(final_report))

    graph.add_edge(START, "request_analyzer")

    graph.add_conditional_edges(
        "request_analyzer",
        _route_after_request_analyzer,
        {
            "investigation_planner": "investigation_planner",
            "final_report": "final_report",
        },
    )

    graph.add_edge("investigation_planner", "tool_executor")
    graph.add_edge("tool_executor", "evidence_analyzer")
    graph.add_edge("evidence_analyzer", "root_cause_analyzer")
    graph.add_edge("root_cause_analyzer", "remediation_planner")
    graph.add_edge("remediation_planner", "approval_gate")

    graph.add_conditional_edges(
        "approval_gate",
        _route_after_approval_gate,
        {
            "remediation_executor": "remediation_executor",
            "final_report": "final_report",
        },
    )

    graph.add_edge("remediation_executor", "verification")
    graph.add_edge("verification", "final_report")
    graph.add_edge("final_report", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_compiled_graph = None


def get_graph():
    """Return the singleton compiled graph (lazy init)."""
    global _compiled_graph
    if _compiled_graph is None:
        logger.info(
            "Building LangGraph workflow",
            extra={"agent_node": "graph", "status": "building"},
        )
        _compiled_graph = build_graph()
        logger.info(
            "LangGraph workflow ready",
            extra={"agent_node": "graph", "status": "ready"},
        )
    return _compiled_graph


def run_investigation(user_request: str, request_id: str | None = None) -> AgentState:
    """Run the full investigation workflow for a user request."""
    import uuid

    req_id = request_id or str(uuid.uuid4())

    # Build the initial full state dict with all required AgentState fields
    initial_state = AgentState(
        request_id=req_id,
        user_request=user_request,
    ).model_dump(mode="json")

    graph = get_graph()
    final_dict = graph.invoke(initial_state)
    return AgentState.model_validate(final_dict)
