from __future__ import annotations

from trace.stages.physical.state import PhysicalState
from trace.tools.tgraph.derive import build_physical_graph
from trace.tools.tgraph.runtime import TGraphRuntime


def prepare_node(state: PhysicalState) -> PhysicalState:
    state["working_graph"] = TGraphRuntime.from_json(build_physical_graph(state["logical_artifact"]["tgraph_logical"])).to_json()
    state["events"] = [*state.get("events", []), {"type": "physical.prepare"}]
    return state
