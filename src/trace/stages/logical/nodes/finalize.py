from __future__ import annotations

from trace.stages.logical.schemas import LogicalArtifact
from trace.stages.logical.state import LogicalState


def finalize_node(state: LogicalState) -> LogicalState:
    artifact = LogicalArtifact.model_validate(state["draft_artifact"]).model_dump(mode="json")
    prior_events = list(state.get("events", []))
    completion_event = {"type": "logical.completed"}
    return {
        "events": [completion_event],
        "result": {
            "stage_id": "logical",
            "artifact": artifact,
            "support_files": state.get("support_files", {}),
            "memory_delta": {},
            "attempts_used": state["attempt"],
            "evaluation_summary": state.get("evaluation_report"),
            "messages": state.get("messages", []),
            "tool_journal": [],
            "repair_history": list(state.get("repair_history", [])),
            "events": [*prior_events, completion_event],
        },
    }
