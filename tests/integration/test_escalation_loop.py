from trace.runtime.engine import TraceRuntime


def test_full_escalation_loop_recovers(tmp_path, monkeypatch):
    runtime = TraceRuntime(output_root=tmp_path)

    call_count = {"ground": 0, "logical": 0, "physical": 0}

    def fake_ground(**kwargs):
        call_count["ground"] += 1
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
            "events": [{"type": "ground.completed", "round": call_count["ground"]}],
            "support_files": {},
        }

    def fake_logical(**kwargs):
        call_count["logical"] += 1
        if call_count["logical"] == 1:
            return {
                "status": "escalated",
                "escalation_report": {
                    "source_stage": "logical",
                    "attempt_at_escalation": 1,
                    "issues": [{"details": {"issue_kind": "logical.escalation.constraint_conflict"}}],
                    "partial_artifact": {},
                },
                "partial_artifact": {"graph": {"nodes": [], "links": []}},
                "evaluation_summary": {"ok": False, "issues": []},
                "attempts_used": 1,
                "messages": [],
                "tool_journal": [],
                "repair_history": [],
                "events": [],
                "support_files": {},
            }
        return {
            "status": "completed",
            "artifact": {"graph": {"nodes": [{"id": "n1"}], "links": []}},
            "evaluation_summary": {"ok": True, "issues": []},
            "attempts_used": 1,
            "messages": [],
            "tool_journal": [],
            "repair_history": [],
            "events": [],
            "support_files": {},
        }

    def fake_physical(**kwargs):
        call_count["physical"] += 1
        return {
            "status": "completed",
            "artifact": {"graph": {"nodes": [], "links": []}, "constraint_files": {}, "checkpoint_files": {}},
            "evaluation_summary": {"ok": True, "issues": []},
            "attempts_used": 1,
            "messages": [],
            "tool_journal": [],
            "repair_history": [],
            "events": [],
            "support_files": {},
        }

    monkeypatch.setattr("trace.runtime.engine.run_ground_stage", fake_ground)
    monkeypatch.setattr("trace.runtime.engine.run_logical_stage", fake_logical)
    monkeypatch.setattr("trace.runtime.engine.run_physical_stage", fake_physical)

    final = runtime.run(intent="x", run_id="escalation-loop")

    assert call_count["ground"] == 2
    assert call_count["logical"] == 2
    assert call_count["physical"] == 1
    assert final["status"] == "completed"
    assert len(final.get("escalation_history", [])) == 1
    assert final["escalation_history"][0]["stage"] == "logical"


def test_escalation_limit_terminates(tmp_path, monkeypatch):
    runtime = TraceRuntime(output_root=tmp_path)

    def fake_ground(**kwargs):
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

    def fake_logical(**kwargs):
        return {
            "status": "escalated",
            "escalation_report": {"source_stage": "logical", "issues": []},
            "partial_artifact": {},
            "evaluation_summary": {"ok": False, "issues": []},
            "attempts_used": 1,
            "messages": [],
            "tool_journal": [],
            "repair_history": [],
            "events": [],
            "support_files": {},
        }

    monkeypatch.setattr("trace.runtime.engine.run_ground_stage", fake_ground)
    monkeypatch.setattr("trace.runtime.engine.run_logical_stage", fake_logical)

    final = runtime.run(intent="x", run_id="escalation-cap")
    assert final["status"] == "failed"
    assert final.get("error", {}).get("type") == "EscalationLimitExceeded"
