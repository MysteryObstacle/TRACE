from unittest.mock import MagicMock, patch

from langgraph.graph import END
from langgraph.types import Command

from trace.runtime.engine import TraceRuntime


def _runtime():
    settings = MagicMock()
    settings.roles = {}
    settings.langsmith.enabled = False
    return TraceRuntime(settings=settings, role_client=MagicMock(), output_root="runs/_tmp_escalation_test")


def test_logical_escalated_routes_back_to_ground(tmp_path):
    runtime = TraceRuntime(output_root=tmp_path)
    state = {
        "run_id": "test",
        "intent": "x",
        "status": "running",
        "artifacts": {"ground": {"graph": {}}},
        "attempt_counters": {},
        "events": [],
        "support_files": {},
    }
    fake_result = {
        "status": "escalated",
        "escalation_report": {
            "source_stage": "logical",
            "issues": [{"details": {"issue_kind": "logical.escalation.constraint_conflict"}}],
        },
        "partial_artifact": {"graph": {}},
        "evaluation_summary": {"ok": False, "issues": []},
        "attempts_used": 2,
        "messages": [],
        "tool_journal": [],
        "repair_history": [],
        "events": [],
        "support_files": {},
    }
    with patch("trace.runtime.engine.run_logical_stage", return_value=fake_result):
        result = runtime._run_logical(state)
    assert isinstance(result, Command)
    assert result.goto == "ground"
    assert result.update["attempt_counters"]["escalation"] == 1
    assert len(result.update["escalation_history"]) == 1
    assert (tmp_path / "test" / "logical-escalation-001" / "artifact.json").exists()


def test_escalation_counter_cap_aborts_to_failed():
    runtime = _runtime()
    state = {
        "run_id": "test",
        "intent": "x",
        "status": "running",
        "artifacts": {"ground": {"graph": {}}},
        "attempt_counters": {"escalation": 2},
        "events": [],
        "support_files": {},
    }
    fake_result = {
        "status": "escalated",
        "escalation_report": {"source_stage": "physical"},
        "partial_artifact": {},
        "evaluation_summary": {"ok": False, "issues": []},
        "attempts_used": 1,
        "messages": [],
        "tool_journal": [],
        "repair_history": [],
        "events": [],
        "support_files": {},
    }
    with patch("trace.runtime.engine.run_physical_stage", return_value=fake_result):
        result = runtime._run_physical(state)
    assert isinstance(result, Command)
    assert result.goto == END
    assert result.update.get("status") == "failed"


def test_ground_consumes_escalation_report_once():
    runtime = _runtime()
    state = {
        "run_id": "test",
        "intent": "x",
        "status": "running",
        "artifacts": {},
        "attempt_counters": {"escalation": 1},
        "events": [],
        "support_files": {},
        "escalation_report": {"source_stage": "logical", "issues": []},
    }
    fake_result = {
        "status": "completed",
        "artifact": {"node_groups": [{"type": "router", "members": ["R1"]}], "constraint_files": {"logical": "ground/logical_constraints.json"}},
        "evaluation_summary": {"ok": True, "issues": []},
        "attempts_used": 1,
        "messages": [],
        "tool_journal": [],
        "retry_history": [],
        "events": [],
        "support_files": {},
    }
    captured_kwargs: dict = {}

    def _capture(**kwargs):
        captured_kwargs.update(kwargs)
        return fake_result

    with patch("trace.runtime.engine.run_ground_stage", side_effect=_capture):
        runtime._run_ground(state)
    assert "escalation_report" in captured_kwargs
    assert captured_kwargs["escalation_report"]["source_stage"] == "logical"


def test_ground_reentry_writes_escalation_snapshot_dir(tmp_path):
    runtime = TraceRuntime(output_root=tmp_path)
    state = {
        "run_id": "ground-esc",
        "intent": "x",
        "status": "running",
        "artifacts": {},
        "attempt_counters": {"escalation": 1},
        "events": [],
        "support_files": {},
        "escalation_report": {"source_stage": "logical", "issues": []},
    }
    fake_result = {
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

    with patch("trace.runtime.engine.run_ground_stage", return_value=fake_result):
        runtime._run_ground(state)

    assert (tmp_path / "ground-esc" / "ground-escalation-001" / "artifact.json").exists()
