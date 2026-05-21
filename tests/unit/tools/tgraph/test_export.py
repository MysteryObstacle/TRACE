from __future__ import annotations

import json

from trace.tools.tgraph.export import export_artifact


def test_export_tgraph_json_returns_normalized_graph():
    artifact = {
        "tgraph_logical": {
            "profile": "logical.v1",
            "nodes": [
                {"id": "B", "type": "router", "label": "B", "ports": [{"id": "p2", "ip": "10.0.0.2", "cidr": "10.0.0.0/30"}]},
                {"id": "A", "type": "router", "label": "A", "ports": [{"id": "p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}]},
            ],
            "links": [{"id": "custom", "from_port": "p2", "to_port": "p1"}],
        }
    }

    result = export_artifact(artifact, target="tgraph-json", stage="logical")

    assert result["ok"] is True
    assert result["files"][0]["path"] == "tgraph.json"
    exported = json.loads(result["files"][0]["content"])
    assert exported["links"][0]["id"] == "p1--p2"


def test_export_unsupported_target_returns_export_error():
    result = export_artifact(
        {"tgraph_logical": {"profile": "logical.v1", "nodes": [], "links": []}},
        target="terraform",
        stage="logical",
    )

    assert result["ok"] is False
    assert result["files"] == []
    assert result["error"]["code"] == "export_error"
