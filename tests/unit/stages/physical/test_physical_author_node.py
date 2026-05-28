from trace.stages.ground.schemas import PHYSICAL_CONSTRAINTS_PATH
from trace.stages.physical.nodes.author import author_node


def test_physical_author_tool_names_include_image_tools() -> None:
    from trace.stages.physical.nodes.author import PhysicalAuthorTools

    state = {"support_files": {"ground/physical_constraints.json": "{}"}}
    tools = PhysicalAuthorTools(state=state, physical_constraints=[]).as_agent_tools()
    names = {tool.name for tool in tools}
    assert "find_images" in names
    assert "get_image" in names


def test_physical_author_node_injects_tgraph_contract() -> None:
    state = {
        "logical_artifact": {"graph": {"stage": "logical", "nodes": [], "links": []}, "checkpoint_files": {}},
        "ground_artifact": {
            "node_groups": [{"type": "computer", "members": ["PLC1"]}],
            "constraint_files": {"physical": PHYSICAL_CONSTRAINTS_PATH},
        },
        "support_files": {
            PHYSICAL_CONSTRAINTS_PATH: (
                '{"pc1": {"kind": "physical.custom", "statement": "PLC1 must have deployable metadata."}}'
            ),
        },
        "events": [],
    }

    class FakeRoleClient:
        def __init__(self) -> None:
            self.calls = []

        def invoke_agent(self, *, role_name, messages, tools, max_react_steps=12):
            self.calls.append({"role_name": role_name, "messages": messages, "tool_names": [_tool_name(tool) for tool in tools]})
            bound = {_tool_name(tool): tool for tool in tools}
            _call_tool(
                bound["write_checkpoint_file"],
                {"content": "def check_pc1(tgraph):\n    return []\n"},
            )
            _call_tool(bound["validate_checkpoint_file"])
            return {"messages": [{"role": "assistant", "content": "done"}]}

    client = FakeRoleClient()
    result = _merge_physical_partial(state, author_node(state, client))
    messages = client.calls[0]["messages"]
    system_content = messages[1]["content"]
    human_content = messages[2]["content"]

    assert messages[1]["role"] == "system"
    assert "[tgraph_contract]" in system_content
    assert "[image_catalog]" not in system_content
    assert "img_pfsense" not in system_content
    assert "[tgraph_contract]" not in human_content
    assert "[image_catalog]" not in human_content
    assert "ground/physical_constraints.json" in human_content
    assert "physical/constraints.json" not in human_content
    assert result["author_output"] == {"checkpoint_files": {"physical": "physical/checkpoints.py"}}
    assert "physical/checkpoints.py" in result["support_files"]


def _tool_name(tool) -> str:
    return getattr(tool, "name", "")


def _call_tool(tool, payload=None):
    if hasattr(tool, "invoke"):
        return tool.invoke(payload or {})
    return tool(**(payload or {}))


def _merge_physical_partial(state: dict, partial: dict) -> dict:
    merged = {**state, **partial}
    if "repair_history" in partial:
        merged["repair_history"] = list(state.get("repair_history", [])) + list(partial["repair_history"])
    if "events" in partial:
        merged["events"] = list(state.get("events", [])) + list(partial["events"])
    return merged
