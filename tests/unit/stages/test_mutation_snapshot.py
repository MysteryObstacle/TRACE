import json
from pathlib import Path

from trace.stages.repair_tools import StageRepairTools


def _seed_logical_graph_dict() -> dict:
    return {
        "stage": "logical",
        "nodes": [{"id": "SW_DMZ", "type": "switch", "label": "SW_DMZ", "ports": []}],
        "links": [],
    }


def test_execute_mutation_file_writes_snapshot(tmp_path):
    artifact = {"graph": _seed_logical_graph_dict(), "constraint_files": {}, "checkpoint_files": {}}
    tools = StageRepairTools(artifact, support_file_root=str(tmp_path))
    write = tools.write_mutation_file(
        content="def mutate(tgraph):\n    tgraph.ensure_subnet('SW_DMZ', cidr='10.10.10.0/24')\n",
        path="logical/mutations/attempt_1.py",
    )
    result = tools.execute_mutation_file(path=write["path"], validate=False)
    snapshot_path = result["summary"]["snapshot_path"]
    assert snapshot_path == "logical/mutations/snapshots/attempt_1.json"
    assert (Path(tmp_path) / snapshot_path).exists()
    snapshot = json.loads((Path(tmp_path) / snapshot_path).read_text(encoding="utf-8"))
    assert snapshot["stage"] == "logical"


def test_execute_mutation_file_failure_does_not_write_snapshot(tmp_path):
    artifact = {"graph": _seed_logical_graph_dict(), "constraint_files": {}, "checkpoint_files": {}}
    tools = StageRepairTools(artifact, support_file_root=str(tmp_path))
    write = tools.write_mutation_file(
        content="def mutate(tgraph):\n    raise RuntimeError('boom')\n",
        path="logical/mutations/attempt_1.py",
    )
    result = tools.execute_mutation_file(path=write["path"], validate=False)
    assert result["ok"] is False
    assert result["summary"]["snapshot_path"] is None
    assert not (Path(tmp_path) / "logical/mutations/snapshots/attempt_1.json").exists()
