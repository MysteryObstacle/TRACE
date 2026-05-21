from trace.stages.physical.nodes.author import author_node


def test_physical_author_node_injects_tgraph_contract():
    state = {
        "logical_artifact": {"tgraph_logical": {"profile": "logical.v1", "nodes": [], "links": []}},
        "ground_artifact": {
            "node_groups": [{"type": "computer", "members": ["PLC1"]}],
            "logical_constraints": [],
            "physical_constraints": [{"id": "pc1", "statement": "PLC1 must have deployable metadata"}],
        },
        "events": [],
    }

    class FakeRoleClient:
        def __init__(self):
            self.calls = []

        def invoke_structured(self, *, role_name, messages, schema):
            self.calls.append({"role_name": role_name, "messages": messages})
            return {"physical_checkpoints": [], "physical_validator_script": None}

    client = FakeRoleClient()
    result = author_node(state, client)
    messages = client.calls[0]["messages"]
    system_content = messages[1]["content"]
    human_content = messages[2]["content"]

    assert messages[1]["role"] == "system"
    assert "[tgraph_contract]" in system_content
    assert "[image_catalog]" in system_content
    assert "img_pfsense" in system_content
    assert "[tgraph_contract]" not in human_content
    assert "[image_catalog]" not in human_content
    assert result["author_output"]["physical_checkpoints"] == []
    assert result["author_output"]["physical_validator_script"] is None
