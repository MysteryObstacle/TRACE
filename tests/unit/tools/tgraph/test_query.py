from trace.tools.tgraph.runtime import TGraphRuntime


def test_runtime_summarizes_graph_shape():
    runtime = TGraphRuntime.from_json(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [], "image": None, "flavor": None},
                {"id": "R1", "type": "router", "label": "R1", "ports": [], "image": None, "flavor": None},
            ],
            "links": [],
        }
    )

    assert runtime.get_graph_summary() == {
        "profile": "logical.v1",
        "node_count": 2,
        "link_count": 0,
    }
    assert runtime.list_nodes() == ["PLC1", "R1"]


def test_runtime_can_list_node_ids_and_neighbors():
    runtime = TGraphRuntime.from_json(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "r1", "type": "router", "label": "r1", "ports": [{"id": "p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
                {"id": "r2", "type": "router", "label": "r2", "ports": [{"id": "p2", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            ],
            "links": [{"id": "p1--p2", "from_port": "p1", "to_port": "p2"}],
        }
    )

    assert runtime.list_nodes() == ["r1", "r2"]
    assert runtime.neighbors("r1") == ["r2"]
