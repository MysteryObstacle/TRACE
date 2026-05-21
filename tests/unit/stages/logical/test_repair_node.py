import json

from trace.stages.logical.nodes import repair as repair_module
from trace.stages.logical.nodes.repair import repair_node


def test_logical_repair_node_uses_agent_tools_and_writes_back_graph():
    state = {
        "draft_artifact": {
            "logical_checkpoints": [],
            "tgraph_logical": {
                "profile": "logical.v1",
                "nodes": [
                    {"id": "r1", "type": "router", "label": "r1", "ports": [], "image": None, "flavor": None},
                    {"id": "r2", "type": "router", "label": "r2", "ports": [], "image": None, "flavor": None},
                ],
                "links": [],
            },
        },
        "evaluation_report": {
            "ok": False,
            "issues": [{"code": "missing_link", "level": "error", "message": "connect r1 and r2"}],
        },
        "attempt": 0,
        "repair_history": [],
        "events": [],
    }

    class FakeRoleClient:
        def __init__(self):
            self.calls = []

        def invoke_agent(self, *, role_name, messages, tools, max_tool_calls=12):
            self.calls.append(
                {
                    "role_name": role_name,
                    "messages": messages,
                    "tool_names": [_tool_name(tool) for tool in tools],
                    "max_tool_calls": max_tool_calls,
                }
            )
            bound = {_tool_name(tool): tool for tool in tools}
            _call_tool(
                bound["add_link"],
                {
                    "from_port": "r1:p1",
                    "to_port": "r2:p1",
                    "from_node": "r1",
                    "to_node": "r2",
                    "from_ip": "10.0.0.1",
                    "from_cidr": "10.0.0.0/30",
                    "to_ip": "10.0.0.2",
                    "to_cidr": "10.0.0.0/30",
                },
            )
            return {"messages": [{"role": "assistant", "content": "repair complete"}]}

    result = repair_node(state, FakeRoleClient())

    assert result["draft_artifact"]["tgraph_logical"]["links"] == [
        {
            "id": "r1:p1--r2:p1",
            "from_port": "r1:p1",
            "to_port": "r2:p1",
            "from_node": "r1",
            "to_node": "r2",
        }
    ]
    assert result["messages"] == [{"role": "assistant", "content": "repair complete"}]
    assert result["attempt"] == 1
    assert result["repair_history"][-1]["mode"] == "agent"


def test_logical_repair_node_injects_logical_constraints_into_prompt():
    state = {
        "ground_artifact": {
            "logical_constraints": [
                {"id": "lc1", "statement": "A must connect to B."},
            ]
        },
        "draft_artifact": {
            "logical_checkpoints": [],
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
        "evaluation_report": {"ok": False, "issues": [{"code": "missing_required_link", "severity": "error", "targets": ["A", "B"]}]},
        "attempt": 0,
        "repair_history": [],
        "events": [],
    }

    class FakeRoleClient:
        def __init__(self):
            self.calls = []

        def invoke_agent(self, *, role_name, messages, tools, max_tool_calls=12):
            self.calls.append({"messages": messages})
            return {"messages": [{"role": "assistant", "content": "noop"}]}

    client = FakeRoleClient()
    repair_node(state, client)
    contents = "\n".join(item["content"] for item in client.calls[0]["messages"] if item["role"] == "human")

    assert "[logical_constraints]" in contents
    assert "A must connect to B." in contents


def test_logical_repair_node_uses_layered_messages_and_system_contract():
    state = {
        "draft_artifact": {
            "logical_checkpoints": [],
            "tgraph_logical": {
                "profile": "logical.v1",
                "nodes": [
                    {"id": "r1", "type": "router", "label": "r1", "ports": [], "image": None, "flavor": None},
                    {"id": "r2", "type": "router", "label": "r2", "ports": [], "image": None, "flavor": None},
                ],
                "links": [],
            },
        },
        "evaluation_report": {"ok": False, "issues": [{"code": "missing_link", "level": "error"}]},
        "attempt": 0,
        "repair_history": [],
        "events": [],
    }

    class FakeRoleClient:
        def __init__(self):
            self.calls = []

        def invoke_agent(self, *, role_name, messages, tools, max_tool_calls=12):
            self.calls.append({"role_name": role_name, "messages": messages})
            return {"messages": [{"role": "assistant", "content": "noop"}]}

    client = FakeRoleClient()
    repair_node(state, client)
    messages = client.calls[0]["messages"]

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "system"
    assert "TGraph contract for this repair round" in messages[1]["content"]
    assert "[evaluation_report]" in messages[3]["content"]
    assert "[evaluation_report_is_latest]" in messages[4]["content"]
    assert "true" in messages[4]["content"].lower()
    assert not any("[tgraph_contract]" in item["content"] for item in messages if item["role"] == "human")


def test_logical_repair_node_injects_recent_repair_ledger():
    state = {
        "draft_artifact": {
            "logical_checkpoints": [],
            "tgraph_logical": {
                "profile": "logical.v1",
                "nodes": [
                    {"id": "r1", "type": "router", "label": "r1", "ports": [], "image": None, "flavor": None},
                    {"id": "r2", "type": "router", "label": "r2", "ports": [], "image": None, "flavor": None},
                ],
                "links": [],
            },
        },
        "evaluation_report": {"ok": False, "issues": [{"code": "missing_link", "level": "error"}]},
        "attempt": 1,
        "repair_history": [
            {
                "round": 1,
                "issue_codes_before": ["missing_link"],
                "resolved_issue_codes": [],
                "remaining_issue_codes": ["missing_link"],
                "new_issue_codes": [],
                "attempted_actions": [{"tool": "add_link", "args": {"from_port": "r1:p1", "to_port": "r2:p1"}}],
                "failed_actions": [{"tool": "add_link", "args": {"from_port": "r1:p1", "to_port": "r2:p1"}}],
            }
        ],
        "events": [],
    }

    class FakeRoleClient:
        def __init__(self):
            self.calls = []

        def invoke_agent(self, *, role_name, messages, tools, max_tool_calls=12):
            self.calls.append({"role_name": role_name, "messages": messages})
            return {"messages": [{"role": "assistant", "content": "noop"}]}

    client = FakeRoleClient()
    repair_node(state, client)
    contents = "\n".join(item["content"] for item in client.calls[0]["messages"] if item["role"] == "human")

    assert "[recent_repair_ledger]" in contents
    assert "missing_link" in contents
    assert "failed_actions" in contents


def test_logical_repair_node_injects_candidate_checkpoints_not_full_set():
    state = {
        "draft_artifact": {
            "logical_checkpoints": [
                {
                    "id": "cp1",
                    "func": "connect_nodes",
                    "description": "WEB must connect to SW_DMZ",
                    "constraint_ids": ["lc1"],
                    "args": {"node_a": "WEB", "node_b": "SW_DMZ"},
                },
                {
                    "id": "cp2",
                    "func": "check_internet_transit_cidr",
                    "description": "INTERNET transit addressing must satisfy 10.0.0.4/30",
                    "constraint_ids": ["lc2"],
                    "args": {"node_id": "INTERNET", "required_cidr": "10.0.0.4/30"},
                },
                {
                    "id": "cp3",
                    "func": "connect_nodes",
                    "description": "BPC1 must connect to SW_BRANCH",
                    "constraint_ids": ["lc3"],
                    "args": {"node_a": "BPC1", "node_b": "SW_BRANCH"},
                },
            ],
            "tgraph_logical": {
                "profile": "logical.v1",
                "nodes": [
                    {"id": "INTERNET", "type": "computer", "label": "INTERNET", "ports": [], "image": None, "flavor": None},
                    {"id": "WEB", "type": "computer", "label": "WEB", "ports": [], "image": None, "flavor": None},
                    {"id": "BPC1", "type": "computer", "label": "BPC1", "ports": [], "image": None, "flavor": None},
                ],
                "links": [],
            },
        },
        "evaluation_report": {
            "ok": False,
            "issues": [
                {
                    "code": "required_cidr_missing",
                    "severity": "error",
                    "message": "INTERNET ports do not satisfy required cidr 10.0.0.4/30 (mode=any)",
                    "targets": ["INTERNET"],
                    "provenance": {
                        "layer": "f4",
                        "source": "authored_check",
                        "check_id": "cp2",
                        "constraint_ids": ["lc2"],
                        "func": "check_internet_transit_cidr",
                        "impl_source": "custom",
                        "args": {"node_id": "INTERNET", "required_cidr": "10.0.0.4/30"},
                    },
                }
            ],
        },
        "attempt": 0,
        "repair_history": [],
        "events": [],
    }

    class FakeRoleClient:
        def __init__(self):
            self.calls = []

        def invoke_agent(self, *, role_name, messages, tools, max_tool_calls=12):
            self.calls.append({"role_name": role_name, "messages": messages, "tool_names": [_tool_name(tool) for tool in tools]})
            return {"messages": [{"role": "assistant", "content": "noop"}]}

    client = FakeRoleClient()
    repair_node(state, client)
    contents = "\n".join(item["content"] for item in client.calls[0]["messages"] if item["role"] == "human")
    tool_names = client.calls[0]["tool_names"]

    assert "[candidate_checkpoints]" in contents
    assert '"id": "cp2"' in contents
    assert '"id": "cp1"' not in contents
    assert '"id": "cp3"' not in contents
    assert "find_checkpoints" in tool_names
    assert "get_checkpoint" in tool_names


def test_logical_repair_node_records_repair_ledger_with_attempts_and_issue_deltas():
    state = {
        "draft_artifact": {
            "logical_checkpoints": [],
            "tgraph_logical": {
                "profile": "logical.v1",
                "nodes": [
                    {"id": "r1", "type": "router", "label": "r1", "ports": [], "image": None, "flavor": None},
                    {"id": "r2", "type": "router", "label": "r2", "ports": [], "image": None, "flavor": None},
                ],
                "links": [],
            },
        },
        "evaluation_report": {
            "ok": False,
            "issues": [{"code": "missing_required_link", "severity": "error", "message": "connect r1 and r2", "targets": ["r1", "r2"]}],
        },
        "attempt": 1,
        "repair_history": [],
        "events": [],
    }

    class FakeRoleClient:
        def invoke_agent(self, *, role_name, messages, tools, max_tool_calls=12):
            bound = {_tool_name(tool): tool for tool in tools}
            payload = {
                "from_port": "r1:p1",
                "to_port": "r2:p1",
                "from_node": "r1",
                "to_node": "r2",
                "from_ip": "10.0.0.1",
                "from_cidr": "10.0.0.0/30",
                "to_ip": "10.0.0.2",
                "to_cidr": "10.0.0.0/30",
            }
            tool_result = _call_tool(bound["add_link"], payload)
            return {
                "messages": [
                    {"type": "ai", "tool_calls": [{"id": "call1", "name": "add_link", "args": payload}]},
                    {"type": "tool", "name": "add_link", "tool_call_id": "call1", "content": json.dumps(tool_result)},
                    {"role": "assistant", "content": "repair complete"},
                ]
            }

    result = repair_node(state, FakeRoleClient())
    ledger = result["repair_history"][-1]

    assert ledger["issue_codes_before"] == ["missing_required_link"]
    assert ledger["resolved_issue_codes"] == ["missing_required_link"]
    assert ledger["remaining_issue_codes"] == []
    assert ledger["new_issue_codes"] == []
    assert ledger["attempted_actions"][0]["tool"] == "add_link"
    assert ledger["failed_actions"] == []


def test_logical_repair_node_writes_back_mutated_checkpoints_and_script():
    state = {
        "ground_artifact": {"logical_constraints": []},
        "draft_artifact": {
            "logical_checkpoints": [
                {
                    "id": "cp1",
                    "func": "connect_nodes",
                    "description": "old description",
                    "constraint_ids": ["lc1"],
                    "args": {"node_a": "A", "node_b": "B"},
                }
            ],
            "logical_validator_script": "def broken_check(tgraph, **kwargs):\n    raise KeyError('boom')\n",
            "tgraph_logical": {
                "profile": "logical.v1",
                "nodes": [
                    {"id": "A", "type": "router", "label": "A", "ports": [], "image": None, "flavor": None},
                    {"id": "B", "type": "router", "label": "B", "ports": [], "image": None, "flavor": None},
                ],
                "links": [],
            },
        },
        "evaluation_report": {"ok": False, "issues": [{"code": "checkpoint_execution_error", "severity": "error", "targets": ["checkpoint:cp1"]}]},
        "attempt": 0,
        "repair_history": [],
        "events": [],
    }

    class FakeRoleClient:
        def invoke_agent(self, *, role_name, messages, tools, max_tool_calls=12):
            bound = {_tool_name(tool): tool for tool in tools}
            _call_tool(bound["update_checkpoint"], {"checkpoint_id": "cp1", "description": "patched"})
            _call_tool(bound["replace_validator_script"], {"script": "def broken_check(tgraph, **kwargs):\n    return []\n"})
            return {
                "messages": [
                    {"role": "assistant", "content": "authored checks repaired"},
                ]
            }

    result = repair_node(state, FakeRoleClient())

    assert result["draft_artifact"]["logical_checkpoints"][0]["description"] == "patched"
    assert result["draft_artifact"]["logical_validator_script"] == "def broken_check(tgraph, **kwargs):\n    return []\n"


def test_logical_repair_node_passes_explicit_field_names_to_bound_tools(monkeypatch):
    captured = {}

    class FakeBoundTools:
        def __init__(self):
            self._artifact = {
                "tgraph_logical": {"profile": "logical.v1", "nodes": [], "links": []},
                "logical_checkpoints": [],
                "logical_validator_script": None,
            }

        def topology_view(self):
            return {"nodes": [], "links": []}

        def tools(self):
            return []

        def artifact_state(self):
            return dict(self._artifact)

        def validate(self):
            return {"ok": True, "issues": []}

    def fake_from_json(cls, graph_json, **kwargs):
        captured["graph_json"] = graph_json
        captured["kwargs"] = kwargs
        return FakeBoundTools()

    monkeypatch.setattr(repair_module.BoundTGraphTools, "from_json", classmethod(fake_from_json))

    state = {
        "ground_artifact": {"logical_constraints": []},
        "draft_artifact": {
            "logical_checkpoints": [{"id": "cp1", "func": "connect_nodes", "description": "x", "constraint_ids": [], "args": {}}],
            "logical_validator_script": None,
            "tgraph_logical": {"profile": "logical.v1", "nodes": [], "links": []},
        },
        "evaluation_report": {"ok": False, "issues": []},
        "attempt": 0,
        "repair_history": [],
        "events": [],
    }

    repair_node(state, type("Client", (), {"invoke_agent": lambda self, **kwargs: {"messages": []}})())

    assert captured["kwargs"]["graph_field"] == "tgraph_logical"
    assert captured["kwargs"]["checkpoints_field"] == "logical_checkpoints"
    assert captured["kwargs"]["validator_script_field"] == "logical_validator_script"
    assert captured["kwargs"]["checkpoints"][0]["id"] == "cp1"


def test_logical_repair_node_preserves_graph_when_tool_operation_fails():
    state = {
        "draft_artifact": {
            "logical_checkpoints": [],
            "tgraph_logical": {
                "profile": "logical.v1",
                "nodes": [
                    {"id": "r1", "type": "router", "label": "r1", "ports": [], "image": None, "flavor": None},
                    {"id": "r2", "type": "router", "label": "r2", "ports": [], "image": None, "flavor": None},
                ],
                "links": [],
            },
        },
        "evaluation_report": {"ok": False, "issues": [{"code": "missing_port", "level": "error"}]},
        "attempt": 0,
        "repair_history": [],
        "events": [],
    }

    class FakeRoleClient:
        def invoke_agent(self, *, role_name, messages, tools, max_tool_calls=12):
            bound = {_tool_name(tool): tool for tool in tools}
            _call_tool(
                bound["add_link"],
                {
                    "from_port": "r1:p1",
                    "to_port": "r2:p1",
                },
            )
            return {"messages": [{"role": "assistant", "content": "stopped early"}]}

    result = repair_node(state, FakeRoleClient())

    assert result["draft_artifact"]["tgraph_logical"]["nodes"][0]["ports"] == []
    assert result["draft_artifact"]["tgraph_logical"]["nodes"][1]["ports"] == []
    assert result["draft_artifact"]["tgraph_logical"]["links"] == []
    assert result["messages"] == [{"role": "assistant", "content": "stopped early"}]


def _tool_name(tool):
    return getattr(tool, "name", getattr(tool, "__name__", type(tool).__name__))


def _call_tool(tool, payload=None):
    invoke = getattr(tool, "invoke", None)
    if callable(invoke):
        if payload is None:
            return invoke({})
        return invoke(payload)
    if payload is None:
        return tool()
    return tool(**payload)
