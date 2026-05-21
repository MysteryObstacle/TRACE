from __future__ import annotations

from trace.stages.ground.schemas import GroundArtifact
from trace.stages.ground.state import GroundState


def finalize_node(state: GroundState) -> GroundState:
    artifact = GroundArtifact.model_validate(state["draft_artifact"]).model_dump(mode="json")
    state["status"] = "completed"
    state["result"] = {
        "stage_id": "ground",
        "artifact": artifact,
        "memory_delta": {},
        "attempts_used": state["attempt"],
        "evaluation_summary": state.get("evaluation_report"),
        "messages": state.get("messages", []),
        "tool_journal": [],
        "retry_history": state.get("retry_history", []),
        "events": [*state.get("events", []), {"type": "ground.completed"}],
    }
    return state
