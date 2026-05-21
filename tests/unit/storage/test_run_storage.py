import json

from langchain_core.messages import SystemMessage

from trace.storage.run_storage import RunStorage


def test_run_storage_writes_debug_friendly_layout(tmp_path):
    storage = RunStorage(tmp_path / "runs")

    storage.initialize_run(
        run_id="run-001",
        run_payload={"run_id": "run-001", "status": "running"},
    )
    storage.write_stage_snapshot(
        run_id="run-001",
        stage_id="logical",
        artifact={"logical_checkpoints": [], "tgraph_logical": {"profile": "logical.v1", "nodes": [], "links": []}},
        evaluation={"ok": True, "issues": []},
        summary={"attempts_used": 1},
        messages=[{"role": "human", "content": "hello"}],
        tool_journal=[{"tool": "get_graph_summary", "ok": True}],
        history_name="repair_history",
        history_entries=[{"round": 1, "action": "none"}],
        events=[{"type": "stage.completed"}],
    )

    run_root = tmp_path / "runs" / "run-001"
    assert (run_root / "run.json").exists()
    assert not (run_root / "shared_memory.json").exists()
    assert (run_root / "logical" / "artifact.json").exists()
    assert (run_root / "logical" / "evaluation.json").exists()
    assert (run_root / "logical" / "summary.json").exists()
    assert (run_root / "logical" / "messages.json").exists()
    assert (run_root / "logical" / "tool_journal.json").exists()
    assert (run_root / "logical" / "repair_history.json").exists()
    assert (run_root / "logical" / "events.jsonl").exists()

    payload = json.loads((run_root / "logical" / "artifact.json").read_text(encoding="utf-8"))
    assert payload["tgraph_logical"]["profile"] == "logical.v1"


def test_run_storage_serializes_langchain_messages(tmp_path):
    storage = RunStorage(tmp_path / "runs")
    storage.initialize_run(run_id="run-002", run_payload={"run_id": "run-002", "status": "running"})

    storage.write_stage_snapshot(
        run_id="run-002",
        stage_id="logical",
        artifact={"tgraph_logical": {"profile": "logical.v1", "nodes": [], "links": []}},
        evaluation={"ok": True, "issues": []},
        summary={"attempts_used": 1},
        messages=[SystemMessage(content="hello")],
        tool_journal=[],
        history_name="repair_history",
        history_entries=[],
        events=[],
    )

    payload = json.loads((tmp_path / "runs" / "run-002" / "logical" / "messages.json").read_text(encoding="utf-8"))
    assert payload[0]["type"] == "system"
    assert payload[0]["content"] == "hello"


def test_run_storage_writes_ground_retry_history_with_stage_specific_name(tmp_path):
    storage = RunStorage(tmp_path / "runs")
    storage.initialize_run(run_id="run-003", run_payload={"run_id": "run-003", "status": "running"})

    storage.write_stage_snapshot(
        run_id="run-003",
        stage_id="ground",
        artifact={"node_groups": [], "logical_constraints": [], "physical_constraints": []},
        evaluation={"passed": False, "issues": [{"code": "x", "message": "y"}]},
        summary={"attempts_used": 2},
        messages=[],
        tool_journal=[],
        history_name="retry_history",
        history_entries=[{"after_attempt": 1, "issues": [{"code": "x", "message": "y"}]}],
        events=[],
    )

    run_root = tmp_path / "runs" / "run-003"
    assert (run_root / "ground" / "retry_history.json").exists()
    assert not (run_root / "ground" / "repair_history.json").exists()
