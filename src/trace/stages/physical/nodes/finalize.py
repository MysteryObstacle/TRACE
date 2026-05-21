from __future__ import annotations

from trace.stages.physical.schemas import PhysicalArtifact
from trace.stages.physical.state import PhysicalState


def finalize_node(state: PhysicalState) -> PhysicalState:
    artifact = PhysicalArtifact.model_validate(state["draft_artifact"]).model_dump(mode="json")
    state["result"] = {
        "stage_id": "physical",
        "artifact": artifact,
        "memory_delta": {},
        "attempts_used": state["attempt"],
        "evaluation_summary": state.get("evaluation_report"),
        "messages": state.get("messages", []),
        "tool_journal": [],
        "repair_history": state.get("repair_history", []),
        "events": [*state.get("events", []), {"type": "physical.completed"}],
    }
    return state
