import json

from trace.stages.physical.nodes import repair as repair_module
from trace.stages.physical.nodes.repair import repair_node


def test_physical_repair_node_uses_agent_tools_and_writes_back_artifact():
    state = {
        "logical_artifact": {
            "tgraph_logical": {
                "profile": "logical.v1",
                "nodes": [
                    {"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [], "image": None, "flavor": None},
                ],
                "links": [],
            }
        },
        "draft_artifact": {
            "physical_checkpoints": [
                {
                    "id": "pc1",
                    "func": "broken_check",
                    "description": "old description",
                    "constraint_ids": ["p1"],
                    "args": {"node_id": "PLC1"},
                }
            ],
            "physical_validator_script": "def broken_check(tgraph, **kwargs):\n    raise KeyError('boom')\n",
            "tgraph_physical": {
                "profile": "taal.default.v1",
                "nodes": [
                    {"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [], "image": None, "flavor": None},
                ],
                "links": [],
            },
        },
        "evaluation_report": {"ok": False, "issues": [{"code": "checkpoint_execution_error", "severity": "error", "targets": ["checkpoint:pc1"]}]},
        "attempt": 0,
        "repair_history": [],
        "events": [],
    }

    class FakeRoleClient:
        def invoke_agent(self, *, role_name, messages, tools, max_tool_calls=12):
            bound = {_tool_name(tool): tool for tool in tools}
            _call_tool(
                bound["update_node"],
                {
                    "node_id": "PLC1",
                    "image": {"id": "img1", "name": "OpenPLC"},
                    "flavor": {"vcpu": 1, "ram": 512, "disk": 4},
                },
            )
            _call_tool(bound["update_checkpoint"], {"checkpoint_id": "pc1", "description": "patched"})
            _call_tool(bound["replace_validator_script"], {"script": "def broken_check(tgraph, **kwargs):\n    return []\n"})
            return {
                "messages": [
                    {"type": "ai", "tool_calls": [{"id": "call1", "name": "update_node", "args": {"node_id": "PLC1"}}]},
                    {"type": "tool", "name": "update_node", "tool_call_id": "call1", "content": json.dumps({"ok": True})},
                    {"role": "assistant", "content": "physical repair complete"},
                ]
            }

    result = repair_node(state, FakeRoleClient())

    node = result["draft_artifact"]["tgraph_physical"]["nodes"][0]
    assert node["image"]["id"] == "img1"
    assert node["flavor"]["vcpu"] == 1
    assert result["draft_artifact"]["physical_checkpoints"][0]["description"] == "patched"
    assert result["draft_artifact"]["physical_validator_script"] == "def broken_check(tgraph, **kwargs):\n    return []\n"
    assert result["messages"][-1]["content"] == "physical repair complete"
    assert result["repair_history"][-1]["mode"] == "agent"


def test_physical_repair_injects_tgraph_contract_and_uses_agent_messages():
    state = {
        "logical_artifact": {
            "tgraph_logical": {
                "profile": "logical.v1",
                "nodes": [{"id": "PLC1", "type": "computer", "label": "PLC1", "ports": []}],
                "links": [],
            }
        },
        "ground_artifact": {"physical_constraints": [{"id": "pc1", "statement": "PLC1 needs an image and flavor."}]},
        "draft_artifact": {
            "physical_checkpoints": [],
            "physical_validator_script": None,
            "tgraph_physical": {
                "profile": "taal.default.v1",
                "nodes": [{"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [], "image": None, "flavor": None}],
                "links": [],
            },
        },
        "evaluation_report": {"ok": False, "issues": [{"code": "computer_image_required", "severity": "error"}]},
        "attempt": 1,
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
    messages = client.calls[0]["messages"]
    human_contents = "\n".join(item["content"] for item in messages if item["role"] == "human")

    assert messages[1]["role"] == "system"
    assert "TGraph contract for this repair round" in messages[1]["content"]
    assert "Image catalog for this repair round" in messages[2]["content"]
    assert "img_pfsense" in messages[2]["content"]
    assert "[tgraph_contract]" not in human_contents
    assert "[image_catalog]" not in human_contents
    assert "[physical_constraints]" in human_contents
    assert "find_checkpoints" in client.calls[0]["tool_names"]
    assert "get_nodes" in client.calls[0]["tool_names"]
    assert "get_links" in client.calls[0]["tool_names"]
    assert "update_node" in client.calls[0]["tool_names"]


def test_physical_repair_node_passes_explicit_field_names_to_bound_tools(monkeypatch):
    captured = {}

    class FakeBoundTools:
        def topology_view(self):
            return {"nodes": [], "links": []}

        def tools(self):
            return []

        def artifact_state(self):
            return {
                "tgraph_physical": {"profile": "taal.default.v1", "nodes": [], "links": []},
                "physical_checkpoints": [],
                "physical_validator_script": None,
            }

        def validate(self):
            return {"ok": True, "issues": []}

    def fake_from_json(cls, graph_json, **kwargs):
        captured["graph_json"] = graph_json
        captured["kwargs"] = kwargs
        return FakeBoundTools()

    monkeypatch.setattr(repair_module.BoundTGraphTools, "from_json", classmethod(fake_from_json))

    state = {
        "logical_artifact": {"tgraph_logical": {"profile": "logical.v1", "nodes": [], "links": []}},
        "ground_artifact": {"physical_constraints": []},
        "draft_artifact": {
            "physical_checkpoints": [{"id": "pc1", "func": "connect_nodes", "description": "x", "constraint_ids": [], "args": {}}],
            "physical_validator_script": None,
            "tgraph_physical": {"profile": "taal.default.v1", "nodes": [], "links": []},
        },
        "evaluation_report": {"ok": False, "issues": []},
        "attempt": 0,
        "repair_history": [],
        "events": [],
    }

    repair_node(state, type("Client", (), {"invoke_agent": lambda self, **kwargs: {"messages": []}})())

    assert captured["kwargs"]["graph_field"] == "tgraph_physical"
    assert captured["kwargs"]["checkpoints_field"] == "physical_checkpoints"
    assert captured["kwargs"]["validator_script_field"] == "physical_validator_script"
    assert captured["kwargs"]["checkpoints"][0]["id"] == "pc1"


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
