from trace.runtime.engine import TraceRuntime


def test_state_sqlite_created_after_run(tmp_path, monkeypatch):
    runtime = TraceRuntime(output_root=tmp_path)

    def _stub(**kwargs):
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


def test_resume_picks_up_from_sqlite_when_present(tmp_path, monkeypatch):
    runtime = TraceRuntime(output_root=tmp_path)

    def _ground(**kwargs):
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

    monkeypatch.setattr("trace.runtime.engine.run_ground_stage", _ground)

    def _logical_fail(**kwargs):
        raise RuntimeError("synthetic failure for resume test")

    monkeypatch.setattr("trace.runtime.engine.run_logical_stage", _logical_fail)
    runtime.run(intent="x", run_id="resume-base")

    sqlite_path = tmp_path / "resume-base" / "state.sqlite"
    assert sqlite_path.exists(), "sqlite must exist after a failed run for resume to use it"
