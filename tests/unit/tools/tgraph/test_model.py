import pytest
from pydantic import ValidationError

from trace.tools.tgraph import TGraphJSON as ExportedTGraphJSON
from trace.tools.tgraph.model import (
    TGraphJSON,
    from_standalone_graph,
    to_standalone_graph,
)
from tgraph import TGraph


def test_tgraph_json_rejects_string_image_and_flavor() -> None:
    payload = {
        "profile": "taal.default.v1",
        "nodes": [
            {
                "id": "PLC1",
                "type": "computer",
                "label": "PLC1",
                "ports": [],
                "image": "quay.io/openplc:latest",
                "flavor": "small",
            }
        ],
        "links": [],
    }

    with pytest.raises(ValidationError):
        TGraphJSON.model_validate(payload)


def test_tgraph_json_accepts_structured_image_and_flavor() -> None:
    payload = {
        "profile": "taal.default.v1",
        "nodes": [
            {
                "id": "PLC1",
                "type": "computer",
                "label": "PLC1",
                "ports": [],
                "image": {"id": "openplc", "name": "OpenPLC"},
                "flavor": {"vcpu": 1, "ram": 512, "disk": 4},
            }
        ],
        "links": [],
    }

    graph = TGraphJSON.model_validate(payload)

    node = graph.nodes[0]
    assert node.image is not None
    assert node.image.id == "openplc"
    assert node.image.name == "OpenPLC"
    assert node.flavor is not None
    assert node.flavor.vcpu == 1
    assert node.flavor.ram == 512
    assert node.flavor.disk == 4


def test_tgraph_json_rejects_edges_alias() -> None:
    payload = {
        "profile": "taal.default.v1",
        "nodes": [],
        "edges": [],
    }

    with pytest.raises(ValidationError):
        TGraphJSON.model_validate(payload)


def test_trace_tgraph_public_import_still_exports_compatibility_model() -> None:
    assert ExportedTGraphJSON is TGraphJSON


def test_standalone_tgraph_uses_canonical_shape_without_profile() -> None:
    graph = TGraph.model_validate({"stage": "logical", "nodes": [], "links": []})

    assert graph.model_dump(mode="json") == {
        "stage": "logical",
        "nodes": [],
        "links": [],
    }


def test_trace_tgraph_model_bridges_to_standalone_graph() -> None:
    trace_graph = TGraphJSON.model_validate(
        {"profile": "taal.default.v1", "nodes": [], "links": []}
    )

    standalone = to_standalone_graph(trace_graph)

    assert isinstance(standalone, TGraph)
    assert standalone.model_dump(mode="json") == {
        "stage": "logical",
        "nodes": [],
        "links": [],
    }


def test_standalone_tgraph_model_bridges_to_trace_graph() -> None:
    standalone = TGraph.model_validate({"stage": "physical", "nodes": [], "links": []})

    trace_graph = from_standalone_graph(standalone)

    assert isinstance(trace_graph, TGraphJSON)
    assert trace_graph.profile == "taal.default.v1"
    assert trace_graph.nodes == []
    assert trace_graph.links == []
