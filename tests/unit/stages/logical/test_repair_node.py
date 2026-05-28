import json

from trace.stages.logical.nodes.repair import repair_node


def test_logical_repair_node_uses_mutation_file_tools_and_writes_back_graph(tmp_path):
    state = {
        "draft_artifact": {
            "graph": {
                "stage": "logical",
                "nodes": [
                    {"id": "R1", "type": "router", "label": "R1", "ports": []},
                    {"id": "R2", "type": "router", "label": "R2", "ports": []},
                ],
                "links": [],
            },
            "constraint_files": {},
            "checkpoint_files": {},
        },
        "support_files": {},
        "support_file_root": str(tmp_path),
        "evaluation_report": {
            "ok": False,
            "issues": [{"message": "R1 must connect to R2", "details": {"issue_kind": "logical.topology.direct.missing_edge"}}],
        },
        "attempt": 0,
        "repair_history": [],
        "events": [],
    }

    class FakeRoleClient:
        def __init__(self):
            self.calls = []

        def invoke_agent(self, *, role_name, messages, tools, max_react_steps=12):
            self.calls.append(
                {
                    "role_name": role_name,
                    "messages": messages,
                    "tool_names": [_tool_name(tool) for tool in tools],
                    "max_react_steps": max_react_steps,
                }
            )
            bound = {_tool_name(tool): tool for tool in tools}
            write_payload = {
                "path": "logical/mutations/attempt_1.py",
                "content": "def mutate(tgraph):\n    tgraph.ensure_direct_link('R1', 'R2')\n",
            }
            write_result = _call_tool(bound["write_mutation_file"], write_payload)
            execute_payload = {"path": "logical/mutations/attempt_1.py", "validate": True}
            execute_result = _call_tool(bound["execute_mutation_file"], execute_payload)
            return {
                "messages": [
                    {"type": "ai", "tool_calls": [{"id": "call1", "name": "write_mutation_file", "args": write_payload}]},
                    {"type": "tool", "name": "write_mutation_file", "tool_call_id": "call1", "content": json.dumps(write_result)},
                    {"type": "ai", "tool_calls": [{"id": "call2", "name": "execute_mutation_file", "args": execute_payload}]},
                    {"type": "tool", "name": "execute_mutation_file", "tool_call_id": "call2", "content": json.dumps(execute_result)},
                    {"role": "assistant", "content": "repair complete"},
                ]
            }

    client = FakeRoleClient()
    result = _merge_logical_partial(state, repair_node(state, client))
    graph = result["draft_artifact"]["graph"]

    assert client.calls[0]["role_name"] == "logical_repair"
    tool_names = set(client.calls[0]["tool_names"])
    assert {
        "inspect_graph",
        "read_support_file",
        "write_checkpoint_file",
        "write_mutation_file",
        "execute_mutation_file",
        "validate_graph",
        "list_support_files",
    }.issubset(tool_names)
    assert "find_images" not in tool_names
    assert "get_image" not in tool_names
    assert graph["links"][0]["id"] == "R1-R2-1"
    assert graph["nodes"][0]["ports"][0]["id"] == "_R2-1"
    assert result["messages"] == [{"role": "assistant", "content": "repair complete"}]
    assert result["attempt"] == 1
    assert result["repair_history"][-1]["attempted_actions"][0]["tool"] == "write_mutation_file"
    assert result["repair_history"][-1]["attempted_actions"][1]["tool"] == "execute_mutation_file"
    assert result["repair_history"][-1]["failed_actions"] == []
    assert result["repair_history"][-1]["produced_files"][0]["file_kind"] == "mutation"
    assert result["repair_history"][-1]["produced_files"][0]["path"] == "logical/mutations/attempt_1.py"
    assert "logical/mutations/attempt_1.py" in result["support_files"]


def test_logical_repair_node_injects_file_refs_and_recent_ledger():
    state = {
        "ground_artifact": {
            "logical_constraints": [
                {"id": "lc1", "statement": "A must connect to B."},
            ]
        },
        "draft_artifact": {
            "graph": {
                "stage": "logical",
                "nodes": [
                    {"id": "A", "type": "router", "label": "A", "ports": []},
                    {"id": "B", "type": "router", "label": "B", "ports": []},
                ],
                "links": [],
            },
            "constraint_files": {"logical": "logical/constraints.json"},
            "checkpoint_files": {"logical": "logical/checkpoints.py"},
        },
        "support_files": {
            "logical/constraints.json": '{"lc1": {"kind": "logical.topology.direct", "statement": "A must connect to B."}}',
            "logical/checkpoints.py": "def check_lc1(tgraph):\n    return tgraph.check_direct_link('A', 'B')\n",
        },
        "evaluation_report": {
            "ok": False,
            "issues": [
                {
                    "message": "A must connect to B",
                    "details": {"issue_kind": "logical.topology.direct.missing_edge", "constraint_id": "lc1"},
                }
            ],
        },
        "attempt": 1,
        "repair_history": [
            {
                "round": 1,
                "issue_kinds_before": ["logical.topology.direct.missing_edge"],
                "resolved_issue_kinds": [],
                "remaining_issue_kinds": ["logical.topology.direct.missing_edge"],
                "new_issue_kinds": [],
                "attempted_actions": [{"tool": "execute_mutation_file", "args": {"path": "logical/mutations/attempt_1.py"}}],
                "failed_actions": [{"tool": "execute_mutation_file", "args": {"path": "logical/mutations/attempt_1.py"}}],
            }
        ],
        "events": [],
    }

    class FakeRoleClient:
        def __init__(self):
            self.calls = []

        def invoke_agent(self, *, role_name, messages, tools, max_react_steps=12):
            self.calls.append({"messages": messages, "tool_names": [_tool_name(tool) for tool in tools]})
            return {"messages": [{"role": "assistant", "content": "noop"}]}

    client = FakeRoleClient()
    repair_node(state, client)
    contents = "\n".join(item["content"] for item in client.calls[0]["messages"] if item["role"] == "human")

    assert "[logical_constraints]" in contents
    assert "A must connect to B." in contents
    assert "[constraint_files]" in contents
    assert "[checkpoint_files]" in contents
    assert "[recent_repair_ledger]" in contents
    assert "failed_actions" in contents
    assert "read_support_file" in client.calls[0]["tool_names"]
    assert "write_checkpoint_file" in client.calls[0]["tool_names"]


def test_logical_repair_node_writes_back_mutated_checkpoint_file():
    state = {
        "draft_artifact": {
            "graph": {
                "stage": "logical",
                "nodes": [
                    {"id": "A", "type": "router", "label": "A", "ports": []},
                    {"id": "B", "type": "router", "label": "B", "ports": []},
                ],
                "links": [],
            },
            "constraint_files": {"logical": "logical/constraints.json"},
            "checkpoint_files": {"logical": "logical/checkpoints.py"},
        },
        "support_files": {
            "logical/constraints.json": '{"lc1": {"kind": "logical.custom", "statement": "custom"}}',
            "logical/checkpoints.py": "def check_lc1(tgraph):\n    raise KeyError('boom')\n",
        },
        "evaluation_report": {"ok": False, "issues": [{"details": {"issue_kind": "checkpoint.execution.exception", "constraint_id": "lc1"}}]},
        "attempt": 0,
        "repair_history": [],
        "events": [],
    }

    class FakeRoleClient:
        def invoke_agent(self, *, role_name, messages, tools, max_react_steps=12):
            bound = {_tool_name(tool): tool for tool in tools}
            _call_tool(
                bound["write_checkpoint_file"],
                {
                    "path": "logical/checkpoints.py",
                    "content": "def check_lc1(tgraph):\n    return []\n",
                },
            )
            return {"messages": [{"role": "assistant", "content": "checkpoint file repaired"}]}

    result = _merge_logical_partial(state, repair_node(state, FakeRoleClient()))

    assert result["support_files"]["logical/checkpoints.py"] == "def check_lc1(tgraph):\n    return []\n"
    assert result["draft_artifact"]["checkpoint_files"] == {"logical": "logical/checkpoints.py"}
    assert "checkpoints" not in result["draft_artifact"]
    assert "validator_script" not in result["draft_artifact"]


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


def _merge_logical_partial(state: dict, partial: dict) -> dict:
    merged = {**state, **partial}
    if "repair_history" in partial:
        merged["repair_history"] = list(state.get("repair_history", [])) + list(partial["repair_history"])
    if "events" in partial:
        merged["events"] = list(state.get("events", [])) + list(partial["events"])
    return merged
