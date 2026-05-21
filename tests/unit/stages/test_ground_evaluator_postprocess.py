from trace.stages.ground.nodes.evaluator import evaluator_node


class StubRoleClient:
    def __init__(self, report):
        self.report = report

    def invoke_structured(self, *, role_name, messages, schema):
        return self.report


def test_evaluator_node_preserves_physical_only_issue_without_code_level_filtering():
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
                    "code": "missing_physical_structure",
                    "message": "No physical constraints are provided.",
                    "location": "physical_constraints",
                }
            ],
            "optimizer_brief": {},
        }
    )

    result = evaluator_node(state, client)

    assert result["evaluation_report"] == {
        "passed": False,
        "issues": [
            {
                "code": "missing_physical_structure",
                "message": "No physical constraints are provided.",
                "location": "physical_constraints",
            }
        ],
        "optimizer_brief": {
            "node_groups": [],
            "logical_constraints": [],
            "physical_constraints": [],
            "notes": [],
        },
    }
    assert result["next_action"] == "author"
    assert result["retry_history"][-1]["issues"][0]["code"] == "missing_physical_structure"


def test_evaluator_node_preserves_nonempty_optimizer_brief_on_pass():
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
            "passed": True,
            "issues": [],
            "optimizer_brief": {
                "node_groups": [{"type": "switch", "members": ["SW1"]}],
                "logical_constraints": [{"id": "lc1", "statement": "PLC1 must connect to SW1."}],
                "physical_constraints": [{"id": "pc1", "statement": "PLC1 must use image openplc."}],
                "notes": ["keep this brief untouched"],
            },
        }
    )

    result = evaluator_node(state, client)

    assert result["evaluation_report"] == {
        "passed": True,
        "issues": [],
        "optimizer_brief": {
            "node_groups": [{"type": "switch", "members": ["SW1"]}],
            "logical_constraints": [{"id": "lc1", "statement": "PLC1 must connect to SW1."}],
            "physical_constraints": [{"id": "pc1", "statement": "PLC1 must use image openplc."}],
            "notes": ["keep this brief untouched"],
        },
    }
    assert result["next_action"] == "finalize"
