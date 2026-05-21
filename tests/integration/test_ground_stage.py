from trace.config.settings import load_settings
from trace.stages.ground import run_ground_stage


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
                    "logical_constraints": [{"id": "l1", "statement": "PLC[1..2] must connect to SWITCH1."}],
                    "physical_constraints": [],
                },
                {
                    "node_groups": [
                        {"type": "computer", "members": ["PLC[1..2]"]},
                        {"type": "switch", "members": ["SWITCH1"]},
                    ],
                    "logical_constraints": [
                        {"id": "l1", "statement": "PLC[1..2] must connect to SWITCH1."}
                    ],
                    "physical_constraints": [{"id": "p1", "statement": "PLCs must receive deployable metadata"}],
                },
            ],
            "ground_evaluator": [
                {
                    "passed": False,
                    "issues": [{"code": "missing_node_coverage", "message": "key nodes are not fully covered by constraints"}],
                    "optimizer_brief": {
                        "node_groups": [],
                        "logical_constraints": [],
                        "physical_constraints": [
                            {"id": "p1", "statement": "PLCs must receive deployable metadata"}
                        ],
                        "notes": [],
                    },
                },
                {
                    "passed": True,
                    "issues": [],
                    "optimizer_brief": {},
                },
            ],
        }
    )

    result = run_ground_stage(
        intent="Build a tiny industrial control network.",
        role_client=client,
        settings=load_settings(),
    )

    assert result["artifact"]["physical_constraints"][0]["id"] == "p1"
    assert result["attempts_used"] == 2
    assert result["memory_delta"] == {}
    assert "retry_history" in result
    assert "repair_history" not in result
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
            {"id": "lc1", "statement": "SW_DMZ represents subnet 10.10.10.0/24."},
            {"id": "lc2", "statement": "WEB must directly connect to SW_DMZ."},
            {"id": "lc3", "statement": "R_CORE must use IP 10.10.10.1/24 on its interface connected to SW_DMZ."},
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
                            "code": "missing_node_coverage",
                            "message": "The artifact omitted explicit node inventory.",
                            "location": "node_groups",
                        }
                    ],
                    "optimizer_brief": {
                        "node_groups": fixed_artifact["node_groups"],
                        "logical_constraints": fixed_artifact["logical_constraints"],
                        "physical_constraints": [],
                        "notes": [],
                    },
                },
                {
                    "passed": True,
                    "issues": [],
                    "optimizer_brief": {},
                },
            ],
        }
    )

    result = run_ground_stage(
        intent="Build a network with fixed nodes R_CORE, SW_DMZ, and WEB.",
        role_client=client,
        settings=load_settings(),
    )

    assert result["artifact"]["node_groups"] == fixed_artifact["node_groups"]
    assert result["attempts_used"] == 2
    assert result["retry_history"][0]["issues"][0]["code"] == "missing_node_coverage"


def test_ground_stage_raises_clear_error_when_evaluator_never_accepts_artifact():
    bad = {
        "node_groups": [{"type": "computer", "members": ["PLC1"]}],
        "logical_constraints": [{"id": "l1", "statement": "PLC1 must connect to SWITCH1."}],
        "physical_constraints": [],
    }
    fail_report = {
        "passed": False,
        "issues": [{"code": "unsupported_requirement", "message": "missing mandatory physical detail"}],
        "optimizer_brief": {
            "node_groups": [],
            "logical_constraints": [],
            "physical_constraints": [{"id": "pc1", "statement": "Add a physical constraint."}],
            "notes": [],
        },
    }
    client = SequenceRoleClient(
        {
            "ground_author": [bad, bad, bad],
            "ground_evaluator": [fail_report, fail_report, fail_report],
        }
    )

    try:
        run_ground_stage(
            intent="Build a tiny industrial control network.",
            role_client=client,
            settings=load_settings(),
        )
    except RuntimeError as exc:
        assert "ground stage exceeded max attempts" in str(exc)
    else:
        raise AssertionError("Expected ground stage failure to raise RuntimeError")
