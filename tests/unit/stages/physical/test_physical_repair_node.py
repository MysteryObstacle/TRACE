import json

from trace.stages.physical.nodes.repair import repair_node


def test_physical_repair_node_uses_mutation_file_tools_and_writes_back_artifact(tmp_path):
    state = {
        "logical_artifact": {
            "graph": {
                "stage": "logical",
                "nodes": [{"id": "PLC1", "type": "computer", "label": "PLC1", "ports": []}],
                "links": [],
            },
            "checkpoint_files": {},
        },
        "draft_artifact": {
            "graph": {
                "stage": "physical",
                "nodes": [{"id": "PLC1", "type": "computer", "label": "PLC1", "ports": []}],
                "links": [],
            },
            "constraint_files": {},
            "checkpoint_files": {},
        },
        "support_files": {},
        "support_file_root": str(tmp_path),
        "evaluation_report": {"ok": False, "issues": [{"details": {"issue_kind": "missing_required_node_field"}}]},
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
                }
            )
            bound = {_tool_name(tool): tool for tool in tools}
            write_payload = {
                "path": "physical/mutations/attempt_1.py",
                "content": (
                    "def mutate(tgraph):\n"
                    "    tgraph.set_image('PLC1', 'img_openplc', name='OpenPLC Runtime')\n"
                    "    tgraph.set_flavor('PLC1', vcpu=1, ram=512, disk=4)\n"
                ),
            }
            write_result = _call_tool(bound["write_mutation_file"], write_payload)
            execute_payload = {"path": "physical/mutations/attempt_1.py", "validate": True}
            execute_result = _call_tool(bound["execute_mutation_file"], execute_payload)
            return {
                "messages": [
                    {"type": "ai", "tool_calls": [{"id": "call1", "name": "write_mutation_file", "args": write_payload}]},
                    {"type": "tool", "name": "write_mutation_file", "tool_call_id": "call1", "content": json.dumps(write_result)},
                    {"type": "ai", "tool_calls": [{"id": "call2", "name": "execute_mutation_file", "args": execute_payload}]},
                    {"type": "tool", "name": "execute_mutation_file", "tool_call_id": "call2", "content": json.dumps(execute_result)},
                    {"role": "assistant", "content": "physical repair complete"},
                ]
            }

    client = FakeRoleClient()
    result = repair_node(state, client)
    node = result["draft_artifact"]["graph"]["nodes"][0]

    tool_names = set(client.calls[0]["tool_names"])
    assert {
        "inspect_graph",
        "read_support_file",
        "write_checkpoint_file",
        "write_mutation_file",
        "execute_mutation_file",
        "validate_graph",
        "list_support_files",
        "find_images",
        "get_image",
    }.issubset(tool_names)
    assert node["image"]["id"] == "img_openplc"
    assert node["flavor"]["vcpu"] == 1
    assert result["messages"][-1]["content"] == "physical repair complete"
    assert result["repair_history"][-1]["attempted_actions"][0]["tool"] == "write_mutation_file"
    assert result["repair_history"][-1]["attempted_actions"][1]["tool"] == "execute_mutation_file"


def test_physical_repair_injects_contract_image_catalog_and_logical_topology():
    state = {
        "logical_artifact": {
            "graph": {
                "stage": "logical",
                "nodes": [{"id": "PLC1", "type": "computer", "label": "PLC1", "ports": []}],
                "links": [],
            },
            "checkpoint_files": {},
        },
        "ground_artifact": {
            "physical_constraints": [
                {"id": "pc1", "kind": "physical.custom", "statement": "PLC1 needs an image and flavor."}
            ]
        },
        "draft_artifact": {
            "graph": {
                "stage": "physical",
                "nodes": [{"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [], "image": None, "flavor": None}],
                "links": [],
            },
            "constraint_files": {"physical": "physical/constraints.json"},
            "checkpoint_files": {"physical": "physical/checkpoints.py"},
        },
        "evaluation_report": {"ok": False, "issues": [{"details": {"issue_kind": "missing_required_node_field"}, "severity": "error"}]},
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
    assert "Image catalog for this repair round" not in (messages[2]["content"] if len(messages) > 2 else "")
    assert all("img_pfsense" not in msg.get("content", "") for msg in messages if msg.get("role") == "human")
    assert "[tgraph_contract]" not in human_contents
    assert "[image_catalog]" not in human_contents
    assert "[logical_topology]" in human_contents
    assert "[physical_constraints]" in human_contents
    assert "[constraint_files]" in human_contents
    assert "[checkpoint_files]" in human_contents
    assert "write_mutation_file" in client.calls[0]["tool_names"]
    assert "execute_mutation_file" in client.calls[0]["tool_names"]


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
