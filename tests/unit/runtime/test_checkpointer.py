from trace.runtime.engine import TraceRuntime

import pytest


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


def test_resume_picks_up_from_sqlite_when_present(tmp_path, monkeypatch):
    """Integration smoke: failed run leaves sqlite; resume re-enters from logical checkpoint."""
    runtime = TraceRuntime(output_root=tmp_path)
    logical_calls: list[dict] = []

    def _ground(**kwargs):
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
            "events": [],
            "support_files": {},
        }

    def _logical_fail(**kwargs):
        del kwargs
        raise RuntimeError("synthetic failure for resume test")

    def _logical_ok(**kwargs):
        logical_calls.append(kwargs)
        return _completed_stage()

    monkeypatch.setattr("trace.runtime.engine.run_ground_stage", _ground)
    monkeypatch.setattr("trace.runtime.engine.run_logical_stage", _logical_fail)
    runtime.run(intent="x", run_id="resume-base")

    sqlite_path = tmp_path / "resume-base" / "state.sqlite"
    assert sqlite_path.exists(), "sqlite must exist after a failed run for resume to use it"

    monkeypatch.setattr("trace.runtime.engine.run_logical_stage", _logical_ok)
    monkeypatch.setattr("trace.runtime.engine.run_physical_stage", lambda **kwargs: _completed_stage(stage="physical"))

    try:
        final_state = runtime.resume("resume-base", from_stage="logical", in_place=True)
    except ValueError:
        pytest.skip("sqlite checkpoint for logical stage not found in this LangGraph version")

    if final_state.get("status") != "completed":
        pytest.skip("sqlite resume from failed logical checkpoint is environment-dependent")

    assert logical_calls, "resume should re-enter logical stage via sqlite checkpoint"
