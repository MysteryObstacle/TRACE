from __future__ import annotations

from trace.stages.logical.schemas import LogicalArtifact
from trace.stages.logical.state import LogicalState


def finalize_node(state: LogicalState) -> LogicalState:
    artifact = LogicalArtifact.model_validate(state["draft_artifact"]).model_dump(mode="json")
    state["result"] = {
        "stage_id": "logical",
        "artifact": artifact,
        "memory_delta": {},
        "attempts_used": state["attempt"],
        "evaluation_summary": state.get("evaluation_report"),
        "messages": state.get("messages", []),
        "tool_journal": [],
        "repair_history": state.get("repair_history", []),
        "events": [*state.get("events", []), {"type": "logical.completed"}],
    }
    return state
