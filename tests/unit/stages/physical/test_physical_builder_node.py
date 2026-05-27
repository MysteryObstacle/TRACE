from trace.stages.physical.nodes.builder import builder_node


def test_physical_builder_uses_agent_mutation_tools_without_working_graph_context(tmp_path) -> None:
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
            "node_groups": [],
            "logical_constraints": [],
            "physical_constraints": [
                {"id": "pc1", "kind": "physical.image.exact", "statement": "PLC1 uses image img_openplc."}
            ],
        },
        "draft_artifact": {
            "graph": {
                "stage": "physical",
                "nodes": [
                    {
                        "id": "PLC1",
                        "type": "computer",
                        "label": "PLC1",
                        "ports": [],
                        "image": {"id": "img_ubuntu_22", "name": "ubuntu-22.04"},
                        "flavor": {"vcpu": 2, "ram": 2048, "disk": 20},
                    }
                ],
                "links": [],
            },
            "constraint_files": {"physical": "physical/constraints.json"},
            "checkpoint_files": {},
        },
        "support_files": {
            "physical/constraints.json": (
                '{"pc1": {"kind": "physical.image.exact", "statement": "PLC1 uses image img_openplc."}}'
            ),
            "physical/checkpoints.py": (
                "def check_pc1(tgraph):\n"
                "    return tgraph.check_image_exact('PLC1', 'img_openplc')\n"
            ),
        },
        "support_file_root": str(tmp_path),
        "author_output": {"checkpoint_files": {"physical": "physical/checkpoints.py"}},
        "attempt": 1,
        "events": [],
    }

    class FakeRoleClient:
        def __init__(self) -> None:
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
            _call_tool(
                bound["write_mutation_file"],
                {
                    "path": "physical/mutations/build.py",
                    "content": "def mutate(tgraph):\n    tgraph.set_image('PLC1', 'img_openplc', name='OpenPLC')\n",
                },
            )
            _call_tool(bound["execute_mutation_file"], {"path": "physical/mutations/build.py", "validate": True})
            return {"messages": [{"role": "assistant", "content": "physical build complete"}]}

    client = FakeRoleClient()
    result = builder_node(state, client)
    messages = client.calls[0]["messages"]
    system_content = "\n".join(item["content"] for item in messages if item["role"] == "system")
    human_content = "\n".join(item["content"] for item in messages if item["role"] == "human")

    assert client.calls[0]["role_name"] == "physical_builder"
    tool_names = set(client.calls[0]["tool_names"])
    assert {
        "inspect_graph",
        "read_support_file",
        "write_mutation_file",
        "execute_mutation_file",
        "validate_graph",
        "list_support_files",
        "find_images",
        "get_image",
    }.issubset(tool_names)
    assert "write_checkpoint_file" not in tool_names
    assert "[tgraph_contract]" in system_content
    assert "[image_catalog]" not in system_content
    assert "img_pfsense" not in system_content
    assert "[tgraph_contract]" not in human_content
    assert "[image_catalog]" not in human_content
    assert "[working_graph]" not in human_content
    assert "[graph_summary]" not in human_content
    assert result["draft_artifact"]["graph"]["nodes"][0]["image"]["id"] == "img_openplc"
    assert result["draft_artifact"]["checkpoint_files"] == {"physical": "physical/checkpoints.py"}
    assert result["draft_artifact"]["constraint_files"] == {"physical": "physical/constraints.json"}
    assert "working_graph" not in result
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
