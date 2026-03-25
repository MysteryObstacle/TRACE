import json

from tools.tgraph.ops.serialize import export_tgraph_json, serialize


def test_serialize_logical_profile_emits_links_and_profile() -> None:
    graph = {"profile": "logical.v1", "nodes": [], "links": []}

    payload = serialize(graph, profile="logical.v1")

    assert payload["profile"] == "logical.v1"
    assert "links" in payload
    assert "edges" not in payload


def test_export_tgraph_json_returns_valid_json_text() -> None:
    graph = {"profile": "logical.v1", "nodes": [], "links": []}

    text = export_tgraph_json(graph, profile="logical.v1")
    payload = json.loads(text)

    assert payload["profile"] == "logical.v1"
