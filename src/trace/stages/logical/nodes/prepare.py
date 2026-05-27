from __future__ import annotations

from trace.stages.ground.schemas import LOGICAL_CONSTRAINTS_PATH
from trace.stages.logical.graph_seed import build_logical_seed_graph
from trace.stages.logical.state import LogicalState


def prepare_node(state: LogicalState) -> LogicalState:
    ground_artifact = state.get("ground_artifact", {})
    graph = build_logical_seed_graph(ground_artifact)
    ground_constraint_files = ground_artifact.get("constraint_files") or {}
    logical_path = ground_constraint_files.get("logical", LOGICAL_CONSTRAINTS_PATH)
    constraint_files = {"logical": logical_path}

    return {
        "draft_artifact": {
            "graph": graph.model_dump(mode="json"),
            "constraint_files": constraint_files,
            "checkpoint_files": {},
        },
        "events": [{"type": "logical.prepare"}],
    }
