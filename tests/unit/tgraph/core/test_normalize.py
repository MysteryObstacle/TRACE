from tgraph import TGraph


def test_normalize_canonicalizes_link_ids_and_endpoint_order():
    from tgraph import normalize_graph

    graph = TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {"id": "B", "type": "computer", "label": "B", "ports": [{"id": "b1"}]},
                {"id": "A", "type": "router", "label": "A", "ports": [{"id": "a1"}]},
            ],
            "links": [{"id": "wrong", "from_node": "B", "from_port": "b1", "to_node": "A", "to_port": "a1"}],
        }
    )

    normalized = normalize_graph(graph)

    assert normalized.links[0].id == "A-B-1"
    assert normalized.links[0].from_port == "a1"
    assert normalized.links[0].to_port == "b1"
    assert normalized.links[0].from_node == "A"
    assert normalized.links[0].to_node == "B"


def test_normalize_sorts_nodes_ports_and_links():
    from tgraph import normalize_graph

    graph = TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {
                    "id": "R2",
                    "type": "router",
                    "label": "R2",
                    "ports": [{"id": "r2p2"}, {"id": "r2p1"}],
                },
                {
                    "id": "R1",
                    "type": "router",
                    "label": "R1",
                    "ports": [{"id": "r1p2"}, {"id": "r1p1"}],
                },
            ],
            "links": [
                    {"id": "z", "from_node": "R2", "from_port": "r2p2", "to_node": "R2", "to_port": "r2p1"},
                    {"id": "a", "from_node": "R1", "from_port": "r1p2", "to_node": "R1", "to_port": "r1p1"},
            ],
        }
    )

    normalized = normalize_graph(graph)

    assert [node.id for node in normalized.nodes] == ["R1", "R2"]
    assert [port.id for port in normalized.nodes[0].ports] == ["r1p1", "r1p2"]
    assert [link.id for link in normalized.links] == ["R1-R1-1", "R2-R2-1"]


def test_normalize_is_idempotent_and_does_not_mutate_input():
    from tgraph import normalize_graph

    graph = TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {"id": "B", "type": "computer", "label": "B", "ports": [{"id": "b1"}]},
                {"id": "A", "type": "router", "label": "A", "ports": [{"id": "a1"}]},
            ],
            "links": [{"id": "wrong", "from_node": "B", "from_port": "b1", "to_node": "A", "to_port": "a1"}],
        }
    )

    normalized = normalize_graph(graph)
    normalized_again = normalize_graph(normalized)

    assert graph.links[0].id == "wrong"
    assert normalized.model_dump(mode="json") == normalized_again.model_dump(mode="json")
