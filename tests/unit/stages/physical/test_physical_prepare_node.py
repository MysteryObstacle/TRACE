import json

from trace.stages.ground.schemas import PHYSICAL_CONSTRAINTS_PATH
from trace.stages.physical.nodes.prepare import prepare_node


def test_physical_prepare_does_not_carry_logical_constraint_files() -> None:
    state = {
        "logical_artifact": {
            "graph": {"stage": "logical", "nodes": [], "links": []},
            "constraint_files": {"logical": "ground/logical_constraints.json"},
            "checkpoint_files": {},
        },
        "ground_artifact": {
            "node_groups": [],
            "constraint_files": {
                "logical": "ground/logical_constraints.json",
                "physical": PHYSICAL_CONSTRAINTS_PATH,
            },
        },
        "support_files": {},
        "events": [],
    }

    result = _merge_physical_partial(state, prepare_node(state))

    assert "logical" not in result["draft_artifact"]["constraint_files"]
    assert result["draft_artifact"]["constraint_files"] == {"physical": PHYSICAL_CONSTRAINTS_PATH}


def test_physical_prepare_copies_logical_graph_with_defaults_and_ground_constraint_refs() -> None:
    state = {
        "logical_artifact": {
            "graph": {
                "stage": "logical",
                "nodes": [{"id": "R1", "type": "router", "label": "R1", "ports": []}],
                "links": [],
            },
            "constraint_files": {"logical": "ground/logical_constraints.json"},
            "checkpoint_files": {"logical": "logical/checkpoints.py"},
        },
        "ground_artifact": {
            "node_groups": [{"type": "router", "members": ["R1"]}],
            "constraint_files": {
                "logical": "ground/logical_constraints.json",
                "physical": PHYSICAL_CONSTRAINTS_PATH,
            },
        },
        "support_files": {
            PHYSICAL_CONSTRAINTS_PATH: json.dumps(
                {
                    "pc1": {
                        "kind": "physical.image.exact",
                        "statement": "R1 uses image img_router_linux.",
                    }
                }
            )
        },
        "events": [],
    }

    result = _merge_physical_partial(state, prepare_node(state))
    graph = result["draft_artifact"]["graph"]

    assert graph["stage"] == "physical"
    assert graph["nodes"][0]["image"]["id"] == "img_router_linux"
    assert graph["nodes"][0]["flavor"] == {"vcpu": 2, "ram": 2048, "disk": 10}
    assert result["draft_artifact"]["constraint_files"]["physical"] == PHYSICAL_CONSTRAINTS_PATH
    assert PHYSICAL_CONSTRAINTS_PATH in result["support_files"]


def _merge_physical_partial(state: dict, partial: dict) -> dict:
    merged = {**state, **partial}
    if "repair_history" in partial:
        merged["repair_history"] = list(state.get("repair_history", [])) + list(partial["repair_history"])
    if "events" in partial:
        merged["events"] = list(state.get("events", [])) + list(partial["events"])
    return merged
