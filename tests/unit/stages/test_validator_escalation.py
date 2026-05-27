from langgraph.graph import END
from langgraph.types import Command


def _physical_state(*, attempt=1, max_attempts=3):
    return {
        "logical_artifact": {"graph": {"nodes": [], "links": []}},
        "draft_artifact": {"graph": {"nodes": [], "links": []}},
        "attempt": attempt,
        "max_attempts": max_attempts,
    }


def test_physical_validator_routes_to_escalate_when_kind_matches(monkeypatch):
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
    assert result.goto == "escalate"
    assert result.update.get("evaluation_report")["issues"][0]["details"]["issue_kind"] == "physical.escalation.no_satisfying_image"


def test_physical_validator_prefers_escalate_when_attempts_exhausted_and_kind_matches(monkeypatch):
    from trace.stages.physical.nodes.validator import validator_node

    monkeypatch.setattr(
        "trace.stages.physical.nodes.validator._validate_physical_artifact",
        lambda *_args, **_kwargs: {
            "ok": False,
            "issues": [{"details": {"issue_kind": "physical.escalation.no_satisfying_image"}}],
        },
    )
    result = validator_node(_physical_state(attempt=3, max_attempts=3))
    assert result.goto == "escalate"


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


def test_logical_validator_routes_to_escalate_when_kind_matches(monkeypatch):
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
    assert result.goto == "escalate"
