from langgraph.graph import END

from trace.stages.logical.nodes.validator import validator_node


def test_logical_validator_routes_f4_authored_check_failures_to_repair(tmp_path) -> None:
    state = {
        "draft_artifact": {
            "constraint_files": {"logical": "ground/logical_constraints.json"},
            "checkpoint_files": {"logical": "logical/checkpoints.py"},
            "graph": {
                "stage": "logical",
                "nodes": [
                    {"id": "A", "type": "router", "label": "A", "ports": []},
                    {"id": "B", "type": "router", "label": "B", "ports": []},
                ],
                "links": [],
            },
        },
        "support_files": {
            "ground/logical_constraints.json": '{"lc1": {"kind": "logical.topology.direct", "statement": "A must connect to B."}}',
            "logical/checkpoints.py": 'def check_lc1(tgraph):\n    return tgraph.check_direct_link("A", "B")\n',
        },
        "support_file_root": str(tmp_path),
        "attempt": 1,
        "max_attempts": 3,
    }

    result = validator_node(state)

    assert result.goto == "repair"
    assert result.update["evaluation_report"]["ok"] is False


def test_logical_validator_routes_checkpoint_execution_errors_to_repair(tmp_path) -> None:
    state = {
        "draft_artifact": {
            "constraint_files": {"logical": "ground/logical_constraints.json"},
            "checkpoint_files": {"logical": "logical/checkpoints.py"},
            "graph": {
                "stage": "logical",
                "nodes": [{"id": "A", "type": "router", "label": "A", "ports": []}],
                "links": [],
            },
        },
        "support_files": {
            "ground/logical_constraints.json": '{"lc1": {"kind": "logical.custom", "statement": "A custom logical fact."}}',
            "logical/checkpoints.py": "def check_lc1(tgraph):\n    raise KeyError('boom')\n",
        },
        "support_file_root": str(tmp_path),
        "attempt": 1,
        "max_attempts": 3,
    }

    result = validator_node(state)

    assert result.goto == "repair"
    assert result.update["evaluation_report"]["ok"] is False
    assert {item["details"]["issue_kind"] for item in result.update["evaluation_report"]["issues"]} >= {
        "checkpoint.execution.exception"
    }
