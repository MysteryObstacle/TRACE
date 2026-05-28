from __future__ import annotations

from trace.stages.ground.schemas import PHYSICAL_CONSTRAINTS_PATH
from trace.stages.physical.graph_seed import build_physical_seed_graph
from trace.stages.physical.state import PhysicalState
from trace.tools.images.catalog import get_image


def prepare_node(state: PhysicalState) -> PhysicalState:
    ground_artifact = state.get("ground_artifact", {})
    graph = build_physical_seed_graph(
        state["logical_artifact"]["graph"],
        defaults_by_type=_defaults_by_node_type(),
    )
    ground_constraint_files = ground_artifact.get("constraint_files") or {}
    constraint_files: dict[str, str] = {}
    physical_path = ground_constraint_files.get("physical")
    if physical_path:
        constraint_files["physical"] = physical_path
    elif _has_physical_constraints(state, ground_artifact):
        constraint_files["physical"] = PHYSICAL_CONSTRAINTS_PATH

    return {
        "draft_artifact": {
            "graph": graph.model_dump(mode="json"),
            "constraint_files": constraint_files,
            "checkpoint_files": {},
        },
        "events": [{"type": "physical.prepare"}],
    }


def _has_physical_constraints(state: PhysicalState, ground_artifact: dict) -> bool:
    path = ground_artifact.get("constraint_files", {}).get("physical")
    if not path:
        return False
    content = (state.get("support_files") or {}).get(path)
    if not content:
        return False
    return content.strip() not in ("", "{}")


def _defaults_by_node_type() -> dict[str, dict]:
    return {
        "computer": _image_default("ubuntu_22"),
        "router": {"image": None, "flavor": None},
        "switch": {"image": None, "flavor": None},
    }


def _image_default(image_id: str) -> dict:
    item = get_image(image_id)
    return {
        "image": item["image"],
        "flavor": item["default_flavor"],
    }
