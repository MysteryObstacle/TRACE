from trace.stages.physical.nodes.validator import validator_node


def test_physical_validator_allows_null_image_on_router_and_switch() -> None:
    state = {
        "logical_artifact": {
            "graph": {
                "stage": "logical",
                "nodes": [
                    {"id": "R1", "type": "router", "label": "R1", "ports": []},
                    {"id": "SW1", "type": "switch", "label": "SW1", "ports": []},
                ],
                "links": [],
            },
            "checkpoint_files": {},
        },
        "draft_artifact": {
            "graph": {
                "stage": "physical",
                "nodes": [
                    {
                        "id": "R1",
                        "type": "router",
                        "label": "R1",
                        "ports": [],
                        "image": None,
                        "flavor": None,
                    },
                    {
                        "id": "SW1",
                        "type": "switch",
                        "label": "SW1",
                        "ports": [],
                        "image": None,
                        "flavor": None,
                    },
                ],
                "links": [],
            },
            "constraint_files": {},
            "checkpoint_files": {},
        },
        "attempt": 1,
        "max_attempts": 3,
        "ground_artifact": {"physical_constraints": []},
        "support_files": {},
    }

    result = validator_node(state)

    assert result.goto == "finalize"
    assert result.update["evaluation_report"]["ok"] is True
    assert not any(
        issue["details"].get("issue_kind") == "missing_required_node_field"
        and "R1" in issue.get("location", "")
        for issue in result.update["evaluation_report"]["issues"]
    )
