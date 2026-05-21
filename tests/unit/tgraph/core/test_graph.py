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

