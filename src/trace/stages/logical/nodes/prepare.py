from __future__ import annotations

from trace.stages.logical.state import LogicalState
from trace.tools.tgraph.derive import build_logical_skeleton, expand_node_groups
from trace.tools.tgraph.runtime import TGraphRuntime


def prepare_node(state: LogicalState) -> LogicalState:
    expanded_nodes = expand_node_groups(state["ground_artifact"]["node_groups"])
    state["working_graph"] = TGraphRuntime.from_json(build_logical_skeleton(expanded_nodes)).to_json()
    state["events"] = [*state.get("events", []), {"type": "logical.prepare"}]
    return state
