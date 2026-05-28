from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from langgraph.graph import END, StateGraph

from trace.stages.common import stage_history_name


def compile_repair_stage_graph(
    state_schema: type,
    *,
    nodes: Mapping[str, Any],
    checkpointer: Any = None,
) -> Any:
    graph = StateGraph(state_schema)
    for name, node in nodes.items():
        graph.add_node(name, node)
    graph.set_entry_point("prepare")
    graph.add_edge("prepare", "author")
    graph.add_edge("author", "builder")
    graph.add_edge("builder", "validator")
    graph.add_edge("repair", "validator")
    graph.add_edge("finalize", END)
    graph.add_edge("escalate", END)
    return graph.compile(checkpointer=checkpointer)


def completed_stage_result(*, stage_id: str, state: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
    prior_events = list(state.get("events", []))
    completion_event = {"type": f"{stage_id}.completed"}
    history_name = stage_history_name(stage_id)
    return {
        "events": [completion_event],
        "result": {
            "stage_id": stage_id,
            "artifact": artifact,
            "support_files": state.get("support_files", {}),
            "memory_delta": {},
            "attempts_used": state["attempt"],
            "evaluation_summary": state.get("evaluation_report"),
            "messages": state.get("messages", []),
            "tool_journal": [],
            history_name: list(state.get(history_name, [])),
            "events": [*prior_events, completion_event],
        },
    }


def escalated_stage_result(*, stage_id: str, state: dict[str, Any]) -> dict[str, object]:
    prior_events = list(state.get("events", []))
    event = {"type": f"{stage_id}.escalated", "attempt": state.get("attempt", 1)}
    history_name = stage_history_name(stage_id)
    return {
        "result": {
            "status": "escalated",
            "stage_id": stage_id,
            "escalation_report": state.get("escalation_report"),
            "partial_artifact": state.get("draft_artifact"),
            "evaluation_summary": state.get("evaluation_report"),
            "attempts_used": state.get("attempt", 1),
            "messages": state.get("messages", []),
            "tool_journal": [],
            history_name: list(state.get(history_name, [])),
            "events": [*prior_events, event],
            "support_files": state.get("support_files", {}),
        },
        "events": [event],
    }


def extract_agent_messages(agent_result: Any) -> list[dict[str, Any]]:
    if isinstance(agent_result, dict):
        messages = agent_result.get("messages")
        if isinstance(messages, list):
            return [item for item in messages if isinstance(item, dict) and item.get("role")]
    return []
