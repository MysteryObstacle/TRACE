import json

import pytest


def _raw_graph() -> dict:
    return {
        "stage": "logical",
        "nodes": [
            {"id": "B", "type": "computer", "label": "B", "ports": [{"id": "b1"}]},
            {"id": "A", "type": "router", "label": "A", "ports": [{"id": "a1"}]},
        ],
        "links": [{"id": "wrong", "from_port": "b1", "to_port": "a1"}],
    }


def test_load_tgraph_accepts_dict_and_normalizes_by_default():
    from tgraph import load_tgraph

    graph = load_tgraph(_raw_graph())

    assert [node.id for node in graph.nodes] == ["A", "B"]
    assert graph.links[0].id == "a1--b1"


def test_load_tgraph_accepts_json_string():
    from tgraph import load_tgraph

    graph = load_tgraph(json.dumps(_raw_graph()))

    assert graph.stage == "logical"
    assert graph.links[0].id == "a1--b1"


def test_load_tgraph_accepts_file_path(tmp_path):
    from tgraph import load_tgraph

    path = tmp_path / "graph.json"
    path.write_text(json.dumps(_raw_graph()), encoding="utf-8")

    graph = load_tgraph(path)

    assert graph.nodes[0].id == "A"


def test_dump_tgraph_returns_stable_dict_and_json_string():
    from tgraph import dump_tgraph, load_tgraph

    graph = load_tgraph(_raw_graph())

    dumped = dump_tgraph(graph)
    dumped_json = dump_tgraph(graph, as_json=True)

    assert dumped == {
        "stage": "logical",
        "nodes": [
            {"id": "A", "type": "router", "label": "A", "ports": [{"id": "a1", "ip": "", "cidr": ""}], "image": None, "flavor": None},
            {"id": "B", "type": "computer", "label": "B", "ports": [{"id": "b1", "ip": "", "cidr": ""}], "image": None, "flavor": None},
        ],
        "links": [{"id": "a1--b1", "from_port": "a1", "to_port": "b1", "from_node": "A", "to_node": "B"}],
    }
    assert json.loads(dumped_json) == dumped


def test_load_tgraph_rejects_unknown_top_level_fields():
    from tgraph import load_tgraph
    from tgraph.core.errors import TGraphError

    with pytest.raises(TGraphError) as exc:
        load_tgraph({"stage": "logical", "nodes": [], "links": [], "metadata": {}})

    assert exc.value.code == "document_error"

