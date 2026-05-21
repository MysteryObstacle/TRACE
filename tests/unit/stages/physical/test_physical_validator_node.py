from trace.stages.physical.nodes.validator import validator_node


def test_physical_validator_executes_physical_checkpoints():
    state = {
        "author_output": {
            "physical_checkpoints": [
                {
                    "id": "pc1",
                    "func": "connect_nodes",
                    "description": "PLC1 connect R1",
                    "constraint_ids": ["p1"],
                    "args": {"node_a": "PLC1", "node_b": "R1"},
                }
            ],
            "physical_validator_script": None,
        },
        "draft_artifact": {
            "physical_checkpoints": [
                {
                    "id": "pc1",
                    "func": "connect_nodes",
                    "description": "PLC1 connect R1",
                    "constraint_ids": ["p1"],
                    "args": {"node_a": "PLC1", "node_b": "R1"},
                }
            ],
            "physical_validator_script": None,
            "tgraph_physical": {
                "profile": "taal.default.v1",
                "nodes": [
                    {
                        "id": "PLC1",
                        "type": "computer",
                        "label": "PLC1",
                        "ports": [],
                        "image": {"id": "img1", "name": "OpenPLC"},
                        "flavor": {"vcpu": 1, "ram": 512, "disk": 4},
                    },
                    {
                        "id": "R1",
                        "type": "router",
                        "label": "R1",
                        "ports": [],
                        "image": None,
                        "flavor": None,
                    },
                ],
                "links": [],
            },
        },
        "logical_artifact": {
            "tgraph_logical": {
                "profile": "logical.v1",
                "nodes": [
                    {"id": "PLC1", "type": "computer", "label": "PLC1", "ports": []},
                    {"id": "R1", "type": "router", "label": "R1", "ports": []},
                ],
                "links": [],
            }
        },
        "attempt": 1,
        "max_attempts": 3,
    }

    result = validator_node(state)

    assert result["evaluation_report"]["ok"] is False
    assert {item["code"] for item in result["evaluation_report"]["issues"]} >= {"missing_required_link"}
    assert result["next_action"] == "repair"
    assert "error" not in result


def test_physical_validator_fails_fast_on_authored_checkpoint_errors():
    state = {
        "author_output": {
            "physical_checkpoints": [
                {
                    "id": "pc1",
                    "func": "broken_check",
                    "description": "broken custom check",
                    "constraint_ids": ["p1"],
                    "args": {},
                }
            ],
            "physical_validator_script": "def broken_check(tgraph, **kwargs):\n    raise KeyError('boom')\n",
        },
        "draft_artifact": {
            "physical_checkpoints": [
                {
                    "id": "pc1",
                    "func": "broken_check",
                    "description": "broken custom check",
                    "constraint_ids": ["p1"],
                    "args": {},
                }
            ],
            "physical_validator_script": "def broken_check(tgraph, **kwargs):\n    raise KeyError('boom')\n",
            "tgraph_physical": {
                "profile": "taal.default.v1",
                "nodes": [
                    {
                        "id": "PLC1",
                        "type": "computer",
                        "label": "PLC1",
                        "ports": [],
                        "image": {"id": "img1", "name": "OpenPLC"},
                        "flavor": {"vcpu": 1, "ram": 512, "disk": 4},
                    }
                ],
                "links": [],
            },
        },
        "logical_artifact": {
            "tgraph_logical": {
                "profile": "logical.v1",
                "nodes": [{"id": "PLC1", "type": "computer", "label": "PLC1", "ports": []}],
                "links": [],
            }
        },
        "attempt": 1,
        "max_attempts": 3,
    }

    result = validator_node(state)

    assert result["next_action"] == "repair"
    assert {item["code"] for item in result["evaluation_report"]["issues"]} >= {"checkpoint_function_runtime_error"}
