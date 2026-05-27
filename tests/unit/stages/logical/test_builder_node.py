from trace.stages.logical.nodes.builder import builder_node


def test_logical_builder_uses_agent_mutation_tools_without_working_graph_context(tmp_path) -> None:
    state = {
        "ground_artifact": {
            "node_groups": [
                {"type": "computer", "members": ["PLC1"]},
                {"type": "switch", "members": ["SW1"]},
            ],
            "logical_constraints": [
                {"id": "lc1", "kind": "logical.topology.direct", "statement": "PLC1 directly connects to SW1."}
            ],
            "physical_constraints": [],
        },
        "draft_artifact": {
            "graph": {
                "stage": "logical",
                "nodes": [
                    {"id": "PLC1", "type": "computer", "label": "PLC1", "ports": []},
                    {"id": "SW1", "type": "switch", "label": "SW1", "ports": []},
                ],
                "links": [],
            },
            "constraint_files": {"logical": "logical/constraints.json"},
            "checkpoint_files": {},
        },
        "support_files": {
            "logical/constraints.json": (
                '{"lc1": {"kind": "logical.topology.direct", "statement": "PLC1 directly connects to SW1."}}'
            )
        },
        "support_file_root": str(tmp_path),
        "author_output": {"checkpoint_files": {"logical": "logical/checkpoints.py"}},
        "attempt": 1,
        "events": [],
    }
    state["support_files"]["logical/checkpoints.py"] = (
        "def check_lc1(tgraph):\n"
        "    return tgraph.check_direct_link('PLC1', 'SW1')\n"
    )

    class FakeRoleClient:
        def __init__(self) -> None:
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
                bound["write_mutation_file"],
                {
                    "path": "logical/mutations/build.py",
                    "content": "def mutate(tgraph):\n    tgraph.ensure_direct_link('PLC1', 'SW1')\n",
                },
            )
            _call_tool(bound["execute_mutation_file"], {"path": "logical/mutations/build.py", "validate": True})
            return {"messages": [{"role": "assistant", "content": "logical build complete"}]}

    client = FakeRoleClient()
    result = builder_node(state, client)
    graph = result["draft_artifact"]["graph"]
    messages = client.calls[0]["messages"]
    human_content = "\n".join(item["content"] for item in messages if item["role"] == "human")

    assert client.calls[0]["role_name"] == "logical_builder"
    assert client.calls[0]["tool_names"] == [
        "inspect_graph",
        "read_support_file",
        "write_mutation_file",
        "execute_mutation_file",
        "validate_graph",
    ]
    assert "write_checkpoint_file" not in client.calls[0]["tool_names"]
    assert graph["links"][0]["id"] == "PLC1-SW1-1"
    assert "logical/mutations/build.py" in result["support_files"]
    assert result["draft_artifact"]["checkpoint_files"] == {"logical": "logical/checkpoints.py"}
    assert result["draft_artifact"]["constraint_files"] == {"logical": "logical/constraints.json"}
    assert "working_graph" not in result
    assert "[working_graph]" not in human_content
    assert "[graph_summary]" in human_content
    assert result["events"][-1] == {"type": "logical.builder.completed", "attempt": 1}


def test_logical_builder_keeps_seed_graph_when_agent_does_not_execute_mutation(tmp_path) -> None:
    state = {
        "ground_artifact": {"node_groups": [], "logical_constraints": [], "physical_constraints": []},
        "draft_artifact": {
            "graph": {
                "stage": "logical",
                "nodes": [
                    {"id": "N1", "type": "router", "label": "N1", "ports": []},
                    {"id": "N2", "type": "router", "label": "N2", "ports": []},
                ],
                "links": [],
            },
            "constraint_files": {"logical": "logical/constraints.json"},
            "checkpoint_files": {},
        },
        "support_files": {"logical/constraints.json": "{}"},
        "support_file_root": str(tmp_path),
        "author_output": {"checkpoint_files": {}},
        "attempt": 1,
        "events": [],
    }

    class FakeRoleClient:
        def invoke_agent(self, *, role_name, messages, tools, max_tool_calls=12):
            return {"messages": [{"role": "assistant", "content": "no mutation needed"}]}

    result = builder_node(state, FakeRoleClient())

    assert result["draft_artifact"]["graph"]["links"] == []
    assert result["draft_artifact"]["constraint_files"] == {"logical": "logical/constraints.json"}
    assert "checkpoints" not in result["draft_artifact"]
    assert "validator_script" not in result["draft_artifact"]


def _tool_name(tool) -> str:
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
