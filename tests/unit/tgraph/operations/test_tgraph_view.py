from tgraph import TGraph
from tgraph.operations.validate.view import TGraphView


def _node_local_graph() -> TGraph:
    return TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {"id": "A", "type": "computer", "label": "A", "ports": [{"id": "_B-1"}, {"id": "_B-2"}]},
                {
                    "id": "B",
                    "type": "switch",
                    "label": "B",
                    "ports": [{"id": "_A-1"}, {"id": "_A-2"}, {"id": "_C-1"}],
                },
                {"id": "C", "type": "computer", "label": "C", "ports": [{"id": "_B-1"}]},
            ],
            "links": [
                {"id": "A-B-primary", "from_node": "A", "from_port": "_B-1", "to_node": "B", "to_port": "_A-1"},
                {"id": "A-B-backup", "from_node": "A", "from_port": "_B-2", "to_node": "B", "to_port": "_A-2"},
                {"id": "B-C-1", "from_node": "C", "from_port": "_B-1", "to_node": "B", "to_port": "_C-1"},
            ],
        }
    )


def test_view_ports_are_node_local() -> None:
    view = TGraphView(_node_local_graph())

    assert view.port("A", "_B-1")["node"] == "A"
    assert view.port("C", "_B-1")["node"] == "C"
    assert view.port("B", "_B-1") is None


def test_view_links_filter_by_node_pair_and_link_key() -> None:
    view = TGraphView(_node_local_graph())

    assert [link["id"] for link in view.links(between=["A", "B"])] == ["A-B-primary", "A-B-backup"]
    assert [link["id"] for link in view.links(between=["A", "B"], link_key="primary")] == ["A-B-primary"]
    assert [link["id"] for link in view.links(node_id="A", port_id="_B-2")] == ["A-B-backup"]


def test_view_paths_use_node_scoped_link_endpoints() -> None:
    view = TGraphView(_node_local_graph())

    assert view.neighbors("A") == ["B"]
    assert view.paths("A", "C") == [["A", "B", "C"]]
