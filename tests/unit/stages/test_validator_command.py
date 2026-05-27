from langgraph.graph import END
from langgraph.types import Command

from trace.stages.logical.nodes.validator import validator_node as logical_validator
from trace.stages.physical.nodes.validator import validator_node as physical_validator


def test_logical_validator_returns_command_finalize_when_ok(monkeypatch):
    monkeypatch.setattr(
        "trace.stages.logical.nodes.validator._validate_logical_artifact",
        lambda *_args, **_kwargs: {"ok": True, "issues": []},
    )
    state = {"draft_artifact": {"graph": {"stage": "logical", "nodes": [], "links": []}}, "attempt": 1, "max_attempts": 3}
    result = logical_validator(state)
    assert isinstance(result, Command)
    assert result.goto == "finalize"
    assert result.update.get("evaluation_report") == {"ok": True, "issues": []}


def test_logical_validator_returns_command_repair_when_not_ok(monkeypatch):
    monkeypatch.setattr(
        "trace.stages.logical.nodes.validator._validate_logical_artifact",
        lambda *_args, **_kwargs: {"ok": False, "issues": [{"details": {"issue_kind": "missing_link"}}]},
    )
    state = {"draft_artifact": {"graph": {"stage": "logical", "nodes": [], "links": []}}, "attempt": 1, "max_attempts": 3}
    result = logical_validator(state)
    assert result.goto == "repair"


def test_logical_validator_returns_command_failed_when_attempts_exhausted(monkeypatch):
    monkeypatch.setattr(
        "trace.stages.logical.nodes.validator._validate_logical_artifact",
        lambda *_args, **_kwargs: {"ok": False, "issues": [{"details": {"issue_kind": "missing_link"}}]},
    )
    state = {"draft_artifact": {"graph": {"stage": "logical", "nodes": [], "links": []}}, "attempt": 3, "max_attempts": 3}
    result = logical_validator(state)
    assert result.goto == END
    assert result.update.get("error") is not None
