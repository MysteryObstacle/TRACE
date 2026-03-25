from pathlib import Path

from tools.tgraph.io.load import load_tgraph


def test_load_tgraph_auto_reads_json_profile(tmp_path: Path) -> None:
    source = tmp_path / "logical.json"
    source.write_text('{"profile": "logical.v1", "nodes": [], "links": []}', encoding="utf-8")

    graph = load_tgraph(source)

    assert graph.profile == "logical.v1"


def test_load_tgraph_gml_stub_is_explicit() -> None:
    try:
        load_tgraph("topology.gml")
    except NotImplementedError as exc:
        assert "import_not_implemented" in str(exc)
    else:
        raise AssertionError("expected a stub loader failure")
