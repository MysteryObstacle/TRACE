from trace.stages.ground.schemas import LOGICAL_CONSTRAINTS_PATH
from trace.stages.logical.nodes.author import author_node


def test_logical_author_node_injects_tgraph_contract() -> None:
    state = {
        "ground_artifact": {
            "node_groups": [{"type": "router", "members": ["R1"]}],
            "constraint_files": {"logical": LOGICAL_CONSTRAINTS_PATH},
        },
        "support_files": {
            LOGICAL_CONSTRAINTS_PATH: (
                '{"lc1": {"kind": "logical.custom", "statement": "R1 must exist."}}'
            ),
        },
        "events": [],
    }

    class FakeRoleClient:
        def __init__(self) -> None:
            self.calls = []

        def invoke_agent(self, *, role_name, messages, tools, max_tool_calls=12):
            self.calls.append({"role_name": role_name, "messages": messages, "tool_names": [_tool_name(tool) for tool in tools]})
            bound = {_tool_name(tool): tool for tool in tools}
            _call_tool(
                bound["write_checkpoint_file"],
                {
                    "content": "def check_lc1(tgraph):\n    return []\n",
                },
            )
            _call_tool(bound["validate_checkpoint_file"])
            return {"messages": [{"role": "assistant", "content": "done"}]}

    client = FakeRoleClient()
    result = author_node(state, client)
    messages = client.calls[0]["messages"]
    system_content = messages[1]["content"]
    human_content = messages[2]["content"]

    assert messages[1]["role"] == "system"
    assert "[tgraph_contract]" in system_content
    assert "[tgraph_contract]" not in human_content
    assert "physical_constraints" not in human_content
    assert "working_graph" not in human_content
    assert "ground/logical_constraints.json" in human_content
    assert "logical/constraints.json" not in human_content
    assert client.calls[0]["role_name"] == "logical_author"
    assert client.calls[0]["tool_names"] == [
        "write_checkpoint_file",
        "remove_checkpoint_file",
        "read_constraint_file",
        "validate_checkpoint_file",
    ]
    assert result["author_output"] == {"checkpoint_files": {"logical": "logical/checkpoints.py"}}
    assert "logical/checkpoints.py" in result["support_files"]


def _tool_name(tool) -> str:
    return getattr(tool, "name", "")


def _call_tool(tool, payload=None):
    if hasattr(tool, "invoke"):
        return tool.invoke(payload or {})
    return tool(**(payload or {}))
