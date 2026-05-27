import json

from trace.config.settings import load_settings
from trace.stages.ground import run_ground_stage
from trace.stages.ground.schemas import LOGICAL_CONSTRAINTS_PATH, PHYSICAL_CONSTRAINTS_PATH


class SequenceRoleClient:
    def __init__(self, responses):
        self.responses = {key: list(value) for key, value in responses.items()}
        self.calls = []

    def invoke_structured(self, *, role_name, messages, schema):
        self.calls.append({"role_name": role_name, "messages": messages, "schema": schema, "tool_count": 0})
        return self.responses[role_name].pop(0)

    def invoke(self, *, role_name, messages, schema=None, tools=None):
        return self.invoke_structured(role_name=role_name, messages=messages, schema=schema)


def test_ground_stage_runs_author_evaluator_retry_loop():
    client = SequenceRoleClient(
        {
            "ground_author": [
                {
                    "node_groups": [{"type": "computer", "members": ["PLC[1..2]"]}],
                    "logical_constraints": [{"id": "l1", "kind": "logical.topology.direct", "statement": "PLC1 connects to SWITCH1."}],
                    "physical_constraints": [],
                },
                {
                    "node_groups": [
                        {"type": "computer", "members": ["PLC[1..2]"]},
                        {"type": "switch", "members": ["SWITCH1"]},
                    ],
                    "logical_constraints": [
                        {
                            "id": "l1",
                            "kind": "logical.topology.star",
                            "statement": "SWITCH1 is the star center for leaves PLC1 and PLC2.",
                        }
                    ],
                    "physical_constraints": [
                        {
                            "id": "p1",
                            "kind": "physical.custom",
                            "statement": "PLCs must receive deployable metadata.",
                        }
                    ],
                },
            ],
            "ground_evaluator": [
                {
                    "passed": False,
                    "issues": [
                        {
                            "message": "key nodes are not fully covered by constraints",
                            "details": {"issue_kind": "ground.semantic.missing_node_coverage"},
                        }
                    ],
                    "notes": ["add physical constraint p1"],
                },
                {"passed": True, "issues": [], "notes": []},
            ],
        }
    )

    result = run_ground_stage(
        intent="Build a tiny industrial control network.",
        role_client=client,
        settings=load_settings(),
    )

    physical = json.loads(result["support_files"][PHYSICAL_CONSTRAINTS_PATH])
    assert physical["p1"]["kind"] == "physical.custom"
    assert result["artifact"]["constraint_files"]["physical"] == PHYSICAL_CONSTRAINTS_PATH
    assert result["attempts_used"] == 2
    assert result["memory_delta"] == {}
    assert "retry_history" in result
    assert [call["role_name"] for call in client.calls] == [
        "ground_author",
        "ground_evaluator",
        "ground_author",
        "ground_evaluator",
    ]


def test_ground_stage_retries_when_author_returns_empty_node_inventory():
    empty_draft = {
        "node_groups": [],
        "logical_constraints": [],
        "physical_constraints": [],
    }
    fixed_artifact = {
        "node_groups": [
            {"type": "router", "members": ["R_CORE"]},
            {"type": "switch", "members": ["SW_DMZ"]},
            {"type": "computer", "members": ["WEB"]},
        ],
        "logical_constraints": [
            {"id": "lc1", "kind": "logical.addressing.subnet", "statement": "SW_DMZ represents subnet 10.10.10.0/24."},
            {"id": "lc2", "kind": "logical.topology.direct", "statement": "WEB directly connects to SW_DMZ."},
        ],
        "physical_constraints": [],
    }
    client = SequenceRoleClient(
        {
            "ground_author": [empty_draft, fixed_artifact],
            "ground_evaluator": [
                {
                    "passed": False,
                    "issues": [
                        {
                            "message": "The artifact omitted explicit node inventory.",
                            "location": "node_groups",
                            "details": {"issue_kind": "ground.semantic.missing_node_coverage"},
                        }
                    ],
                    "notes": ["restore node_groups from intent"],
                },
                {"passed": True, "issues": [], "notes": []},
            ],
        }
    )

    result = run_ground_stage(
        intent="Build a network with fixed nodes R_CORE, SW_DMZ, and WEB.",
        role_client=client,
        settings=load_settings(),
    )

    assert result["artifact"]["node_groups"] == fixed_artifact["node_groups"]
    assert LOGICAL_CONSTRAINTS_PATH in result["support_files"]
    assert result["attempts_used"] == 2
    assert result["retry_history"][0]["issues"][0]["details"]["issue_kind"] == "ground.semantic.missing_node_coverage"


def test_ground_stage_raises_clear_error_when_evaluator_never_accepts_artifact():
    bad = {
        "node_groups": [{"type": "computer", "members": ["PLC1"]}],
        "logical_constraints": [
            {"id": "l1", "kind": "logical.topology.direct", "statement": "PLC1 connects to SWITCH1."}
        ],
        "physical_constraints": [],
    }
    fail_report = {
        "passed": False,
        "issues": [
            {
                "message": "missing mandatory physical detail",
                "details": {"issue_kind": "ground.semantic.missing_physical_constraint"},
            }
        ],
        "notes": ["add a physical constraint"],
    }
    client = SequenceRoleClient(
        {
            "ground_author": [bad, bad, bad],
            "ground_evaluator": [fail_report, fail_report, fail_report],
        }
    )

    try:
        run_ground_stage(
            intent="Build a network.",
            role_client=client,
            settings=load_settings(),
        )
        raise AssertionError("expected ground stage to fail")
    except RuntimeError as exc:
        assert "ground stage did not produce a result" in str(exc) or "max attempts" in str(exc)
