import pytest
from pydantic import ValidationError

from trace.tools.tgraph.model import TGraphJSON


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
