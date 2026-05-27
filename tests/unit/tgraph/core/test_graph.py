import pytest
from pydantic import ValidationError


def test_tgraph_package_imports_public_api():
    import tgraph

    assert hasattr(tgraph, "TGraph")
    assert hasattr(tgraph, "GraphStage")


def test_minimal_tgraph_document_shape():
    from tgraph import TGraph

    graph = TGraph.model_validate({"stage": "logical", "nodes": [], "links": []})

    assert graph.stage == "logical"
    assert graph.nodes == []
    assert graph.links == []
    assert graph.model_dump(mode="json") == {
        "stage": "logical",
        "nodes": [],
        "links": [],
    }


def test_rejects_deferred_header_fields():
    from tgraph import TGraph

    for field in ("schema_version", "profile", "metadata"):
        with pytest.raises(ValidationError):
            TGraph.model_validate({"stage": "logical", "nodes": [], "links": [], field: {}})


def test_ports_are_node_local_when_links_include_nodes():
    from tgraph import TGraph

    graph = TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {"id": "A", "type": "computer", "label": "A", "ports": [{"id": "_B-1"}]},
                {"id": "B", "type": "switch", "label": "B", "ports": [{"id": "_A-1"}, {"id": "_C-1"}]},
                {"id": "C", "type": "computer", "label": "C", "ports": [{"id": "_B-1"}]},
            ],
            "links": [
                {"id": "A-B-1", "from_node": "A", "from_port": "_B-1", "to_node": "B", "to_port": "_A-1"},
                {"id": "B-C-1", "from_node": "C", "from_port": "_B-1", "to_node": "B", "to_port": "_C-1"},
            ],
        }
    )

    assert graph.links[0].from_node == "A"
    assert graph.links[1].from_node == "C"


def test_rejects_new_links_without_node_scoped_endpoints():
    from tgraph import TGraph

    with pytest.raises(ValidationError):
        TGraph.model_validate(
            {
                "stage": "logical",
                "nodes": [
                    {"id": "A", "type": "computer", "label": "A", "ports": [{"id": "_B-1"}]},
                    {"id": "B", "type": "switch", "label": "B", "ports": [{"id": "_A-1"}]},
                ],
                "links": [{"id": "A-B-1", "from_port": "_B-1", "to_port": "_A-1"}],
            }
        )


def test_rejects_node_ids_with_dash_delimiter():
    from tgraph import TGraph

    with pytest.raises(ValidationError):
        TGraph.model_validate(
            {
                "stage": "logical",
                "nodes": [{"id": "SW-DMZ", "type": "switch", "label": "SW-DMZ"}],
                "links": [],
            }
        )
