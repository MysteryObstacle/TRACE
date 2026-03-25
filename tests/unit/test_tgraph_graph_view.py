from tools.tgraph.graph_view import to_networkx


def _sample_graph() -> dict:
    return {
        "profile": "logical.v1",
        "nodes": [
            {"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [{"id": "PLC1:eth0", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            {"id": "SW1", "type": "switch", "label": "SW1", "ports": [{"id": "SW1:ge0/1", "ip": "", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
        ],
        "links": [{"id": "PLC1:eth0--SW1:ge0/1", "from_port": "PLC1:eth0", "to_port": "SW1:ge0/1", "from_node": "PLC1", "to_node": "SW1"}],
    }


def test_to_networkx_preserves_link_metadata() -> None:
    view = to_networkx(_sample_graph())

    edge = next(iter(view.edges(data=True, keys=True)))

    assert edge[0] == "PLC1"
    assert edge[1] == "SW1"
    assert edge[2] == "PLC1:eth0--SW1:ge0/1"
    assert edge[3]["link_id"] == "PLC1:eth0--SW1:ge0/1"
    assert edge[3]["from_port"] == "PLC1:eth0"
    assert edge[3]["to_port"] == "SW1:ge0/1"


def test_to_networkx_uses_node_ids_as_graph_nodes() -> None:
    view = to_networkx(_sample_graph())

    assert sorted(view.nodes) == ["PLC1", "SW1"]
