import json

from trace.stages.ground.schemas import LOGICAL_CONSTRAINTS_PATH
from trace.stages.logical.nodes.prepare import prepare_node


def test_logical_prepare_seeds_graph_and_references_ground_constraint_files() -> None:
    state = {
        "ground_artifact": {
            "node_groups": [{"type": "computer", "members": ["PLC1"]}],
            "constraint_files": {"logical": LOGICAL_CONSTRAINTS_PATH},
        },
        "support_files": {
            LOGICAL_CONSTRAINTS_PATH: json.dumps(
                {
                    "lc1": {
                        "kind": "logical.topology.direct",
                        "statement": "PLC1 directly connects to SW1.",
                    }
                }
            )
        },
        "events": [],
    }

    result = prepare_node(state)

    graph = result["draft_artifact"]["graph"]
    assert graph["stage"] == "logical"
    assert result["draft_artifact"]["constraint_files"] == {"logical": LOGICAL_CONSTRAINTS_PATH}
    assert result["draft_artifact"]["checkpoint_files"] == {}
    assert LOGICAL_CONSTRAINTS_PATH in state["support_files"]


def test_logical_prepare_does_not_carry_physical_constraint_files() -> None:
    state = {
        "ground_artifact": {
            "node_groups": [{"type": "computer", "members": ["PLC1"]}],
            "constraint_files": {
                "logical": LOGICAL_CONSTRAINTS_PATH,
                "physical": "ground/physical_constraints.json",
            },
        },
        "support_files": {},
        "events": [],
    }

    result = prepare_node(state)

    assert result["draft_artifact"]["constraint_files"] == {"logical": LOGICAL_CONSTRAINTS_PATH}


def test_logical_prepare_expands_node_groups_with_existing_behavior() -> None:
    grounded = {
        "node_groups": [{"type": "computer", "members": ["PLC[1..2]"]}],
        "constraint_files": {"logical": LOGICAL_CONSTRAINTS_PATH},
    }

    result = prepare_node({"ground_artifact": grounded, "events": [], "support_files": {}})

    assert [node["id"] for node in result["draft_artifact"]["graph"]["nodes"]] == ["PLC1", "PLC2"]
