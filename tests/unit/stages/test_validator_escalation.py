from langgraph.graph import END
from langgraph.types import Command


def _physical_state(*, attempt=1, max_attempts=3):
    return {
        "logical_artifact": {"graph": {"nodes": [], "links": []}},
        "draft_artifact": {"graph": {"nodes": [], "links": []}},
        "attempt": attempt,
        "max_attempts": max_attempts,
    }


def test_physical_validator_routes_escalation_kind_to_repair(monkeypatch):
    from trace.stages.physical.nodes.validator import validator_node

    monkeypatch.setattr(
        "trace.stages.physical.nodes.validator._validate_physical_artifact",
        lambda *_args, **_kwargs: {
            "ok": False,
            "issues": [{"details": {"issue_kind": "physical.escalation.no_satisfying_image"}}],
        },
    )
    result = validator_node(_physical_state(attempt=1, max_attempts=3))
    assert isinstance(result, Command)
    assert result.goto == "repair"
    assert result.update.get("evaluation_report")["issues"][0]["details"]["issue_kind"] == "physical.escalation.no_satisfying_image"
    assert "escalation_report" not in result.update


def test_physical_validator_routes_escalation_kind_to_repair_even_when_attempts_exhausted(monkeypatch):
    from trace.stages.physical.nodes.validator import validator_node

    monkeypatch.setattr(
        "trace.stages.physical.nodes.validator._validate_physical_artifact",
        lambda *_args, **_kwargs: {
            "ok": False,
            "issues": [{"details": {"issue_kind": "physical.escalation.no_satisfying_image"}}],
        },
    )
    result = validator_node(_physical_state(attempt=3, max_attempts=3))
    assert result.goto == "repair"


def test_physical_validator_falls_back_to_failed_when_attempts_exhausted_without_escalation_kind(monkeypatch):
    from trace.stages.physical.nodes.validator import validator_node

    monkeypatch.setattr(
        "trace.stages.physical.nodes.validator._validate_physical_artifact",
        lambda *_args, **_kwargs: {
            "ok": False,
            "issues": [{"details": {"issue_kind": "physical.missing_field"}}],
        },
    )
    result = validator_node(_physical_state(attempt=3, max_attempts=3))
    assert result.goto == END
    assert result.update.get("error") is not None


def test_physical_validator_does_not_escalate_when_ok(monkeypatch):
    from trace.stages.physical.nodes.validator import validator_node

    monkeypatch.setattr(
        "trace.stages.physical.nodes.validator._validate_physical_artifact",
        lambda *_args, **_kwargs: {"ok": True, "issues": []},
    )
    result = validator_node(_physical_state(attempt=1, max_attempts=3))
    assert result.goto == "finalize"


def test_logical_validator_routes_escalation_kind_to_repair(monkeypatch):
    from trace.stages.logical.nodes.validator import validator_node

    monkeypatch.setattr(
        "trace.stages.logical.nodes.validator._validate_logical_artifact",
        lambda *_args, **_kwargs: {
            "ok": False,
            "issues": [{"details": {"issue_kind": "logical.escalation.constraint_conflict"}}],
        },
    )
    state = {"draft_artifact": {"graph": {}}, "attempt": 1, "max_attempts": 3}
    result = validator_node(state)
    assert result.goto == "repair"
    assert "escalation_report" not in result.update
