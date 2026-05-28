from trace.stages.physical.nodes.validator import validator_node


def test_physical_validator_passes_logical_reference_graph_to_tgraph_validate() -> None:
    state = {
        "logical_artifact": {
            "graph": {
                "stage": "logical",
                "nodes": [{"id": "R1", "type": "router", "label": "R1", "ports": []}],
                "links": [],
            },
            "checkpoint_files": {},
        },
        "draft_artifact": {
            "graph": {"stage": "physical", "nodes": [], "links": []},
            "constraint_files": {},
            "checkpoint_files": {},
        },
        "attempt": 1,
        "max_attempts": 3,
        "ground_artifact": {"physical_constraints": []},
    }

    result = validator_node(state)

    assert result.goto == "repair"
    assert result.update["evaluation_report"]["ok"] is False
    assert any(
        issue["details"]["issue_kind"] == "missing_preserved_node"
        for issue in result.update["evaluation_report"]["issues"]
    )


def test_physical_validator_routes_script_exceptions_to_repair(tmp_path) -> None:
    state = {
        "draft_artifact": {
            "constraint_files": {"physical": "ground/physical_constraints.json"},
            "checkpoint_files": {"physical": "physical/checkpoints.py"},
            "graph": {
                "stage": "physical",
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
            "graph": {
                "stage": "logical",
                "nodes": [{"id": "PLC1", "type": "computer", "label": "PLC1", "ports": []}],
                "links": [],
            },
            "checkpoint_files": {},
        },
        "support_files": {
            "ground/physical_constraints.json": '{"pc1": {"kind": "physical.custom", "statement": "PLC1 custom physical fact."}}',
            "physical/checkpoints.py": "def check_pc1(tgraph):\n    raise KeyError('boom')\n",
        },
        "support_file_root": str(tmp_path),
        "attempt": 1,
        "max_attempts": 3,
        "ground_artifact": {
            "physical_constraints": [
                {"id": "pc1", "kind": "physical.custom", "statement": "PLC1 custom physical fact."}
            ]
        },
    }

    result = validator_node(state)

    assert result.goto == "repair"
    assert {item["details"]["issue_kind"] for item in result.update["evaluation_report"]["issues"]} >= {
        "checkpoint.execution.exception"
    }


def test_physical_validator_routes_escalation_issues_to_repair_not_escalate(tmp_path) -> None:
    graph = {
        "stage": "physical",
        "nodes": [
            {
                "id": "PLC1",
                "type": "computer",
                "label": "PLC1",
                "ports": [],
                "image": {"id": "img1", "name": "Image"},
                "flavor": {"vcpu": 1, "ram": 512, "disk": 4},
            }
        ],
        "links": [],
    }
    state = {
        "draft_artifact": {
            "constraint_files": {"physical": "ground/physical_constraints.json"},
            "checkpoint_files": {"physical": "physical/checkpoints.py"},
            "graph": graph,
        },
        "logical_artifact": {"graph": {"stage": "logical", "nodes": [{"id": "PLC1", "type": "computer", "label": "PLC1", "ports": []}], "links": []}},
        "support_files": {
            "ground/physical_constraints.json": '{"pc1": {"kind": "physical.custom", "statement": "unavailable image"}}',
            "physical/checkpoints.py": (
                "def check_pc1(tgraph):\n"
                "    return tgraph.escalate('physical.escalation.no_satisfying_image', 'no image')\n"
            ),
        },
        "support_file_root": str(tmp_path),
        "attempt": 1,
        "max_attempts": 3,
        "ground_artifact": {"physical_constraints": [{"id": "pc1", "kind": "physical.custom", "statement": "unavailable image"}]},
    }

    result = validator_node(state)

    assert result.goto == "repair"
    assert result.update["evaluation_report"]["issues"][0]["details"]["issue_kind"] == "physical.escalation.no_satisfying_image"
