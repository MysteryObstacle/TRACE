from trace.stages.physical.nodes.builder import builder_node


def test_physical_builder_injects_tgraph_contract():
    state = {
        "logical_artifact": {
            "tgraph_logical": {
                "profile": "logical.v1",
                "nodes": [{"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [], "image": None, "flavor": None}],
                "links": [],
            }
        },
        "ground_artifact": {"node_groups": [], "logical_constraints": [], "physical_constraints": []},
        "working_graph": {
            "profile": "taal.default.v1",
            "nodes": [{"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [], "image": None, "flavor": None}],
            "links": [],
        },
        "author_output": {"physical_checkpoints": [], "physical_validator_script": None},
        "attempt": 1,
    }

    class FakeRoleClient:
        def __init__(self):
            self.calls = []

        def invoke_structured(self, *, role_name, messages, schema):
            self.calls.append({"role_name": role_name, "messages": messages})
            return {
                "physical_checkpoints": [],
                "physical_validator_script": None,
                "tgraph_physical": {
                    "profile": "taal.default.v1",
                    "nodes": [{"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [], "image": None, "flavor": None}],
                    "links": [],
                },
            }

    client = FakeRoleClient()
    result = builder_node(state, client)
    messages = client.calls[0]["messages"]
    system_content = messages[1]["content"]
    human_content = messages[2]["content"]

    assert messages[1]["role"] == "system"
    assert "[tgraph_contract]" in system_content
    assert "[image_catalog]" in system_content
    assert "img_pfsense" in system_content
    assert "[tgraph_contract]" not in human_content
    assert "[image_catalog]" not in human_content
    assert result["draft_artifact"]["tgraph_physical"]["profile"] == "taal.default.v1"
    assert result["draft_artifact"]["physical_validator_script"] is None
