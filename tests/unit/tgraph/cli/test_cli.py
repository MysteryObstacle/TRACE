import json

from typer.testing import CliRunner

from tgraph.cli.main import app


runner = CliRunner()


def _write_graph(tmp_path):
    path = tmp_path / "graph.json"
    path.write_text(
        json.dumps(
            {
                "stage": "logical",
                "nodes": [
                    {"id": "R1", "type": "router", "label": "R1", "ports": [{"id": "r1p1"}]},
                    {"id": "SW1", "type": "switch", "label": "SW1", "ports": [{"id": "sw1p1"}]},
                ],
                "links": [{"id": "r1p1--sw1p1", "from_port": "r1p1", "to_port": "sw1p1"}],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_cli_validate_outputs_json(tmp_path):
    graph = _write_graph(tmp_path)

    result = runner.invoke(app, ["validate", str(graph), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True


def test_cli_inspect_outputs_summary_json(tmp_path):
    graph = _write_graph(tmp_path)

    result = runner.invoke(app, ["inspect", str(graph), "--view", "summary", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["node_count"] == 2


def test_cli_patch_outputs_result_json(tmp_path):
    graph = _write_graph(tmp_path)
    patch = tmp_path / "patch.json"
    patch.write_text(json.dumps({"graph_patch": [{"op": "ensure_node", "id": "APP", "type": "computer", "label": "APP"}]}), encoding="utf-8")

    result = runner.invoke(app, ["patch", str(graph), str(patch), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["diff"]["nodes_added"] == ["APP"]


def test_cli_normalize_writes_output(tmp_path):
    graph = _write_graph(tmp_path)
    out = tmp_path / "normalized.json"

    result = runner.invoke(app, ["normalize", str(graph), "--out", str(out)])

    assert result.exit_code == 0
    assert json.loads(out.read_text(encoding="utf-8"))["links"][0]["from_node"] == "R1"


def test_cli_export_json_writes_output(tmp_path):
    graph = _write_graph(tmp_path)
    out = tmp_path / "exported.json"

    result = runner.invoke(app, ["export", "json", str(graph), "--out", str(out)])

    assert result.exit_code == 0
    assert json.loads(out.read_text(encoding="utf-8"))["stage"] == "logical"


def test_cli_emit_terraform_returns_not_implemented(tmp_path):
    graph = _write_graph(tmp_path)

    result = runner.invoke(app, ["emit", "terraform", str(graph), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "target_not_implemented"

