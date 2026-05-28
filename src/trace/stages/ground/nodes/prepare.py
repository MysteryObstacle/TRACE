from __future__ import annotations

from trace.stages.ground.state import GroundState


def prepare_node(state: GroundState) -> GroundState:
    return {"status": "authoring", "events": [{"type": "ground.prepare"}]}
