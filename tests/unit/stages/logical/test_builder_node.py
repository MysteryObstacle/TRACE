from trace.stages.logical.nodes.builder import builder_node
from trace.tools.tgraph.derive import build_logical_skeleton


def test_logical_builder_passes_node_only_skeleton_and_uses_model_topology():
    state = {
        "ground_artifact": {
            "node_groups": [
                {"type": "computer", "members": ["PLC1", "PLC2"]},
                {"type": "switch", "members": ["SW1"]},
                {"type": "router", "members": ["R1"]},
            ],
            "logical_constraints": [
                {"id": "lc1", "statement": "PLC1 must connect to SW1."},
                {"id": "lc2", "statement": "PLC2 must connect to SW1."},
                {"id": "lc3", "statement": "SW1 must connect to R1."},
            ],
            "physical_constraints": [],
        },
        "attempt": 1,
        "working_graph": build_logical_skeleton(
            [
                {"id": "PLC1", "type": "computer", "label": "PLC1"},
                {"id": "PLC2", "type": "computer", "label": "PLC2"},
                {"id": "SW1", "type": "switch", "label": "SW1"},
                {"id": "R1", "type": "router", "label": "R1"},
            ]
        ),
        "author_output": {"logical_checkpoints": [], "logical_validator_script": None},
    }

    class FakeRoleClient:
        def __init__(self):
            self.calls = []

        def invoke_structured(self, *, role_name, messages, schema):
            self.calls.append({"role_name": role_name, "messages": messages})
            return {
                "tgraph_logical": {
                    "profile": "logical.v1",
                    "nodes": [
                        {
                            "id": "PLC1",
                            "type": "computer",
                            "label": "PLC1",
                            "ports": [{"id": "PLC1_p0", "ip": "192.168.1.11", "cidr": "192.168.1.0/24"}],
                            "image": None,
                            "flavor": None,
                        },
                        {
                            "id": "SW1",
                            "type": "switch",
                            "label": "SW1",
                            "ports": [
                                {"id": "SW1_p0", "ip": "", "cidr": "192.168.1.0/24"},
                                {"id": "SW1_p1", "ip": "", "cidr": "192.168.1.0/24"},
                                {"id": "SW1_p2", "ip": "", "cidr": "192.168.1.0/24"},
                            ],
                            "image": None,
                            "flavor": None,
                        },
                        {
                            "id": "PLC2",
                            "type": "computer",
                            "label": "PLC2",
                            "ports": [{"id": "PLC2_p0", "ip": "192.168.1.12", "cidr": "192.168.1.0/24"}],
                            "image": None,
                            "flavor": None,
                        },
                        {
                            "id": "R1",
                            "type": "router",
                            "label": "R1",
                            "ports": [{"id": "R1_p0", "ip": "192.168.1.1", "cidr": "192.168.1.0/24"}],
                            "image": None,
                            "flavor": None,
                        },
                    ],
                    "links": [
                        {"id": "PLC1_p0--SW1_p0", "from_port": "PLC1_p0", "to_port": "SW1_p0"},
                        {"id": "PLC2_p0--SW1_p1", "from_port": "PLC2_p0", "to_port": "SW1_p1"},
                        {"id": "R1_p0--SW1_p2", "from_port": "R1_p0", "to_port": "SW1_p2"},
                    ],
                },
            }

    client = FakeRoleClient()
    result = builder_node(state, client)
    graph = result["draft_artifact"]["tgraph_logical"]
    node_ids = sorted(node["id"] for node in graph["nodes"])
    messages = client.calls[0]["messages"]
    system_content = messages[1]["content"]
    human_content = messages[2]["content"]

    assert node_ids == ["PLC1", "PLC2", "R1", "SW1"]
    assert len(graph["links"]) == 3
    assert "[logical_constraints]" in human_content
    assert messages[1]["role"] == "system"
    assert "[tgraph_contract]" in system_content
    assert "[tgraph_contract]" not in human_content
    assert "[builder_mode]" not in human_content
    assert result["working_graph"]["links"] == []
    assert sum(len(node["ports"]) for node in result["working_graph"]["nodes"]) == 0
    assert result["events"][-1] == {"type": "logical.builder.completed", "attempt": 1}


def test_logical_builder_omits_builder_mode_and_keeps_model_output():
    state = {
        "ground_artifact": {"node_groups": [], "logical_constraints": [], "physical_constraints": []},
        "attempt": 1,
        "working_graph": build_logical_skeleton(
            [
                {"id": "n1", "type": "router", "label": "n1"},
                {"id": "n2", "type": "router", "label": "n2"},
            ]
        ),
        "author_output": {
            "logical_checkpoints": [{"id": "cp1", "func": "path_exists", "description": "intent", "constraint_ids": [], "args": {"source_id": "n1", "target_id": "n2"}}],
            "logical_validator_script": None,
        },
    }

    class FakeRoleClient:
        def __init__(self):
            self.calls = []

        def invoke_structured(self, *, role_name, messages, schema):
            self.calls.append({"role_name": role_name, "messages": messages})
            return {
                "tgraph_logical": {
                    "profile": "logical.v1",
                    "nodes": [
                        {"id": "n1", "type": "router", "label": "n1", "ports": [{"id": "n1:p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}], "image": None, "flavor": None},
                        {"id": "n2", "type": "router", "label": "n2", "ports": [{"id": "n2:p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/30"}], "image": None, "flavor": None},
                    ],
                    "links": [{"id": "n1:p1--n2:p1", "from_port": "n1:p1", "to_port": "n2:p1"}],
                },
            }

    client = FakeRoleClient()
    result = builder_node(state, client)
    graph = result["draft_artifact"]["tgraph_logical"]
    messages = client.calls[0]["messages"]
    system_content = messages[1]["content"]
    human_content = messages[2]["content"]

    assert len(graph["links"]) == 1
    assert messages[1]["role"] == "system"
    assert "[tgraph_contract]" in system_content
    assert "[tgraph_contract]" not in human_content
    assert "[builder_mode]" not in human_content
