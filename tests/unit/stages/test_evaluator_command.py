from langgraph.graph import END
from langgraph.types import Command

from trace.stages.ground.nodes.evaluator import evaluator_node


def test_ground_evaluator_returns_command_finalize_when_passed(monkeypatch):
    monkeypatch.setattr(
        "trace.stages.ground.nodes.evaluator.structural_issues_from_draft",
        lambda _draft: [],
    )
    monkeypatch.setattr(
        "trace.stages.ground.nodes.evaluator.invoke_role",
        lambda **_kwargs: ([], {"passed": True, "issues": [], "notes": []}),
    )
    state = {"draft_artifact": {}, "attempt": 1, "max_attempts": 3}
    result = evaluator_node(state, role_client=object())
    assert isinstance(result, Command)
    assert result.goto == "finalize"
    assert result.update["evaluation_report"]["passed"] is True


def test_ground_evaluator_returns_command_author_when_not_passed(monkeypatch):
    monkeypatch.setattr(
        "trace.stages.ground.nodes.evaluator.structural_issues_from_draft",
        lambda _draft: [],
    )
    monkeypatch.setattr(
        "trace.stages.ground.nodes.evaluator.invoke_role",
        lambda **_kwargs: ([], {"passed": False, "issues": [{"message": "x", "details": {"issue_kind": "ground.semantic.missing_node"}}], "notes": []}),
    )
    state = {"draft_artifact": {}, "attempt": 1, "max_attempts": 3, "retry_history": []}
    result = evaluator_node(state, role_client=object())
    assert result.goto == "author"
    assert result.update["attempt"] == 2
    assert len(result.update["retry_history"]) == 1


def test_ground_evaluator_returns_command_failed_when_attempts_exhausted(monkeypatch):
    monkeypatch.setattr(
        "trace.stages.ground.nodes.evaluator.structural_issues_from_draft",
        lambda _draft: [{"message": "bad"}],
    )
    monkeypatch.setattr(
        "trace.stages.ground.nodes.evaluator.invoke_role",
        lambda **_kwargs: ([], {"passed": False, "issues": [], "notes": []}),
    )
    state = {"draft_artifact": {}, "attempt": 3, "max_attempts": 3}
    result = evaluator_node(state, role_client=object())
    assert result.goto == END
    assert result.update.get("error") is not None
