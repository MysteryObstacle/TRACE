from __future__ import annotations

from trace.stages.ground.schemas import (
    GroundArtifact,
    LOGICAL_CONSTRAINTS_PATH,
    PHYSICAL_CONSTRAINTS_PATH,
    draft_constraints_to_file_payload,
)
from trace.stages.ground.state import GroundState
from trace.stages.support_files import write_support_json


def finalize_node(state: GroundState) -> GroundState:
    draft = state.get("draft_artifact", {})
    logical_payload = draft_constraints_to_file_payload(draft.get("logical_constraints", []))
    physical_payload = draft_constraints_to_file_payload(draft.get("physical_constraints", []))

    write_support_json(state, LOGICAL_CONSTRAINTS_PATH, logical_payload)

    constraint_files: dict[str, str] = {"logical": LOGICAL_CONSTRAINTS_PATH}
    if physical_payload:
        write_support_json(state, PHYSICAL_CONSTRAINTS_PATH, physical_payload)
        constraint_files["physical"] = PHYSICAL_CONSTRAINTS_PATH

    artifact = GroundArtifact(
        node_groups=draft.get("node_groups", []),
        constraint_files=constraint_files,
    ).model_dump(mode="json")

    prior_events = list(state.get("events", []))
    completion_event = {"type": "ground.completed"}
    return {
        "status": "completed",
        "events": [completion_event],
        "result": {
            "stage_id": "ground",
            "artifact": artifact,
            "support_files": state.get("support_files", {}),
            "memory_delta": {},
            "attempts_used": state["attempt"],
            "evaluation_summary": state.get("evaluation_report"),
            "messages": state.get("messages", []),
            "tool_journal": [],
            "retry_history": list(state.get("retry_history", [])),
            "events": [*prior_events, completion_event],
        },
    }
