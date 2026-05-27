from trace.stages.ground.nodes.evaluator import evaluator_node


class StubRoleClient:
    def __init__(self, report):
        self.report = report

    def invoke_structured(self, *, role_name, messages, schema):
        return self.report


def test_evaluator_node_merges_structural_and_semantic_issues():
    state = {
        "attempt": 1,
        "max_attempts": 3,
        "draft_artifact": {
            "node_groups": [{"type": "computer", "members": ["PLC1"]}],
            "logical_constraints": [{"id": "lc1", "statement": "missing kind field"}],
            "physical_constraints": [],
        },
        "retry_history": [],
        "events": [],
    }
    client = StubRoleClient(
        {
            "passed": True,
            "issues": [],
            "notes": [],
        }
    )

    result = evaluator_node(state, client)

    assert result["evaluation_report"]["passed"] is False
    assert result["evaluation_report"]["issues"]
    assert result["next_action"] == "author"


def test_evaluator_node_finalize_when_semantic_pass_and_structure_ok():
    state = {
        "attempt": 1,
        "max_attempts": 3,
        "draft_artifact": {
            "node_groups": [{"type": "computer", "members": ["PLC1"]}],
            "logical_constraints": [
                {"id": "lc1", "kind": "logical.topology.direct", "statement": "PLC1 connects to SW1."}
            ],
            "physical_constraints": [],
        },
        "retry_history": [],
        "events": [],
    }
    client = StubRoleClient({"passed": True, "issues": [], "notes": []})

    result = evaluator_node(state, client)

    assert result["evaluation_report"]["passed"] is True
    assert result["next_action"] == "finalize"


def test_evaluator_node_records_notes_on_retry():
    state = {
        "attempt": 1,
        "max_attempts": 3,
        "draft_artifact": {
            "node_groups": [{"type": "computer", "members": ["PLC1"]}],
            "logical_constraints": [],
            "physical_constraints": [],
        },
        "retry_history": [],
        "events": [],
    }
    client = StubRoleClient(
        {
            "passed": False,
            "issues": [
                {
                    "message": "missing WEB",
                    "details": {"issue_kind": "ground.semantic.missing_node"},
                }
            ],
            "notes": ["add WEB"],
        }
    )

    result = evaluator_node(state, client)

    assert result["next_action"] == "author"
    assert result["retry_history"][-1]["notes"] == ["add WEB"]
