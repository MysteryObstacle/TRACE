from trace.stages.logical.nodes.author import author_node


def test_logical_author_node_injects_tgraph_contract():
    state = {
        "ground_artifact": {
            "node_groups": [{"type": "router", "members": ["R1"]}],
            "logical_constraints": [{"id": "lc1", "statement": "R1 must connect to R2."}],
            "physical_constraints": [],
        },
        "events": [],
    }

    class FakeRoleClient:
        def __init__(self):
            self.calls = []

        def invoke_structured(self, *, role_name, messages, schema):
            self.calls.append({"role_name": role_name, "messages": messages})
            return {
                "logical_checkpoints": [],
                "logical_validator_script": None,
            }

    client = FakeRoleClient()
    result = author_node(state, client)
    messages = client.calls[0]["messages"]
    system_content = messages[1]["content"]
    human_content = messages[2]["content"]

    assert messages[1]["role"] == "system"
    assert "[tgraph_contract]" in system_content
    assert "[tgraph_contract]" not in human_content
    assert result["author_output"]["logical_checkpoints"] == []
