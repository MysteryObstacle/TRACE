from trace.runtime.engine import TraceRuntime
from trace.runtime.stage_checkpoint import StageCheckpointUnavailable


def _completed_stage(*, artifact=None, stage="logical"):
    if artifact is None:
        artifact = {
            "graph": {"stage": stage, "nodes": [], "links": []},
            "constraint_files": {"logical": "ground/logical_constraints.json"},
            "checkpoint_files": {stage: f"{stage}/checkpoints.py"},
        }
    return {
        "status": "completed",
        "artifact": artifact,
        "evaluation_summary": {"ok": True, "issues": []},
        "attempts_used": 1,
        "messages": [],
        "tool_journal": [],
        "retry_history": [],
        "repair_history": [],
        "events": [],
        "support_files": {},
    }


def test_state_sqlite_created_after_run(tmp_path, monkeypatch):
    runtime = TraceRuntime(output_root=tmp_path)

    def _stub(**kwargs):
        del kwargs
        return {
            "status": "completed",
            "artifact": {
                "node_groups": [{"type": "router", "members": ["R1"]}],
                "constraint_files": {"logical": "ground/logical_constraints.json"},
            },
            "evaluation_summary": {"ok": True, "issues": []},
            "attempts_used": 1,
            "messages": [],
            "tool_journal": [],
            "retry_history": [],
            "repair_history": [],
            "events": [],
            "support_files": {},
        }

    monkeypatch.setattr("trace.runtime.engine.run_ground_stage", _stub)
    monkeypatch.setattr("trace.runtime.engine.run_logical_stage", _stub)
    monkeypatch.setattr("trace.runtime.engine.run_physical_stage", _stub)

    runtime.run(intent="x", run_id="ckpt-001")
    assert (tmp_path / "ckpt-001" / "state.sqlite").exists()


def test_resume_uses_sqlite_path_when_in_place(tmp_path, monkeypatch):
    runtime = TraceRuntime(output_root=tmp_path)
    sqlite_resume_called = {"value": False}

    def _spy_resume_via_sqlite(**kwargs):
        sqlite_resume_called["value"] = True
        return {
            "run_id": kwargs["target_run_id"],
            "intent": "x",
            "status": "completed",
            "current_stage": None,
            "artifacts": {},
            "events": [{"type": "run.completed"}],
        }

    monkeypatch.setattr(runtime, "_resume_via_sqlite", _spy_resume_via_sqlite)

    run_id = "resume-route"
    run_root = tmp_path / run_id
    run_root.mkdir(parents=True)
    (run_root / "state.sqlite").write_bytes(b"")
    runtime.storage.initialize_run(
        run_id=run_id,
        run_payload={"run_id": run_id, "intent": "x", "status": "failed", "current_stage": "logical"},
    )

    final_state = runtime.resume(run_id, from_stage="logical", in_place=True)

    assert sqlite_resume_called["value"] is True
    assert final_state.get("status") == "completed"


def test_resume_prefers_nested_stage_sqlite_when_in_place(tmp_path, monkeypatch):
    runtime = TraceRuntime(output_root=tmp_path)
    calls = {"stage": False, "outer": False}

    def _stage_resume(**kwargs):
        calls["stage"] = True
        return {
            "run_id": kwargs["target_run_id"],
            "intent": "x",
            "status": "completed",
            "current_stage": None,
            "artifacts": {},
            "events": [{"type": "run.completed"}],
        }

    def _outer_resume(**_kwargs):
        calls["outer"] = True
        return {"run_id": "outer", "status": "completed"}

    monkeypatch.setattr(runtime, "_resume_via_stage_sqlite", _stage_resume, raising=False)
    monkeypatch.setattr(runtime, "_resume_via_sqlite", _outer_resume)

    run_id = "nested-route"
    run_root = tmp_path / run_id
    (run_root / "logical").mkdir(parents=True)
    (run_root / "state.sqlite").write_bytes(b"outer")
    (run_root / "logical" / "state.sqlite").write_bytes(b"inner")
    runtime.storage.initialize_run(
        run_id=run_id,
        run_payload={"run_id": run_id, "intent": "x", "status": "failed", "current_stage": "logical"},
    )

    final_state = runtime.resume(run_id, from_stage="logical", in_place=True)

    assert calls == {"stage": True, "outer": False}
    assert final_state.get("status") == "completed"


def test_resume_falls_back_to_outer_sqlite_when_nested_stage_sqlite_unavailable(tmp_path, monkeypatch):
    runtime = TraceRuntime(output_root=tmp_path)
    calls = {"stage": False, "outer": False}

    def _stage_resume(**_kwargs):
        calls["stage"] = True
        raise StageCheckpointUnavailable("synthetic unreadable stage checkpoint")

    def _outer_resume(**kwargs):
        calls["outer"] = True
        return {
            "run_id": kwargs["target_run_id"],
            "status": "completed",
            "events": [{"type": "run.completed"}],
        }

    monkeypatch.setattr(runtime, "_resume_via_stage_sqlite", _stage_resume)
    monkeypatch.setattr(runtime, "_resume_via_sqlite", _outer_resume)

    run_id = "resume-fallback"
    run_root = tmp_path / run_id
    (run_root / "logical").mkdir(parents=True)
    (run_root / "state.sqlite").write_bytes(b"outer")
    (run_root / "logical" / "state.sqlite").write_bytes(b"unreadable")
    runtime.storage.initialize_run(
        run_id=run_id,
        run_payload={"run_id": run_id, "intent": "x", "status": "failed", "current_stage": "logical"},
    )

    final_state = runtime.resume(run_id, from_stage="logical", in_place=True)

    assert calls == {"stage": True, "outer": True}
    assert final_state["status"] == "completed"


def test_stage_sqlite_unavailable_does_not_overwrite_run_state_before_fallback(tmp_path, monkeypatch):
    runtime = TraceRuntime(output_root=tmp_path)
    run_id = "resume-stage-unavailable"
    original_state = {"run_id": run_id, "intent": "x", "status": "failed", "current_stage": "logical"}
    runtime.storage.initialize_run(run_id=run_id, run_payload=original_state)

    def _unavailable_graph(*_args, **_kwargs):
        raise StageCheckpointUnavailable("synthetic unreadable stage checkpoint")

    monkeypatch.setattr(runtime, "_build_run_graph", _unavailable_graph)

    try:
        runtime._resume_via_stage_sqlite(source_run_id=run_id, target_run_id=run_id, resume_stage="logical")
    except StageCheckpointUnavailable:
        pass

    assert runtime.storage.read_run_state(run_id) == original_state
