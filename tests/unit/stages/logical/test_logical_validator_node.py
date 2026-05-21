from trace.stages.logical.nodes.validator import validator_node


def test_logical_validator_routes_f4_authored_check_failures_to_repair():
    state = {
        "author_output": {
            "logical_checkpoints": [
                {
                    "id": "cp1",
                    "func": "connect_nodes",
                    "description": "A connect B",
                    "constraint_ids": ["lc1"],
                    "args": {"node_a": "A", "node_b": "B"},
                }
            ],
            "logical_validator_script": None,
        },
        "draft_artifact": {
            "logical_checkpoints": [
                {
                    "id": "cp1",
                    "func": "connect_nodes",
                    "description": "A connect B",
                    "constraint_ids": ["lc1"],
                    "args": {"node_a": "A", "node_b": "B"},
                }
            ],
            "logical_validator_script": None,
            "tgraph_logical": {
                "profile": "logical.v1",
                "nodes": [
                    {"id": "A", "type": "router", "label": "A", "ports": [], "image": None, "flavor": None},
                    {"id": "B", "type": "router", "label": "B", "ports": [], "image": None, "flavor": None},
                ],
                "links": [],
            },
        },
        "attempt": 1,
        "max_attempts": 3,
    }

    result = validator_node(state)

    assert result["evaluation_report"]["ok"] is False
    assert result["next_action"] == "repair"


def test_logical_validator_routes_checkpoint_execution_errors_to_repair():
    state = {
        "author_output": {
            "logical_checkpoints": [
                {
                    "id": "cp1",
                    "func": "broken_check",
                    "description": "broken custom check",
                    "constraint_ids": ["lc1"],
                    "args": {},
                }
            ],
            "logical_validator_script": "def broken_check(tgraph, **kwargs):\n    raise KeyError('boom')\n",
        },
        "draft_artifact": {
            "logical_checkpoints": [
                {
                    "id": "cp1",
                    "func": "broken_check",
                    "description": "broken custom check",
                    "constraint_ids": ["lc1"],
                    "args": {},
                }
            ],
            "logical_validator_script": "def broken_check(tgraph, **kwargs):\n    raise KeyError('boom')\n",
            "tgraph_logical": {
                "profile": "logical.v1",
                "nodes": [{"id": "A", "type": "router", "label": "A", "ports": [], "image": None, "flavor": None}],
                "links": [],
            },
        },
        "attempt": 1,
        "max_attempts": 3,
    }

    result = validator_node(state)

    assert result["evaluation_report"]["ok"] is False
    assert {item["code"] for item in result["evaluation_report"]["issues"]} >= {"checkpoint_function_runtime_error"}
    assert result["next_action"] == "repair"
