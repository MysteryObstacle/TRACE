from __future__ import annotations

from trace.stages.ground.state import GroundState


def prepare_node(state: GroundState) -> GroundState:
    state["status"] = "authoring"
    state["events"] = [*state.get("events", []), {"type": "ground.prepare"}]
    return state
