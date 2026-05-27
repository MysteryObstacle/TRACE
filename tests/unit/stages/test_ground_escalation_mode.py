from langgraph.graph import END
from langgraph.types import Command


def test_author_node_includes_escalation_section_when_report_present(monkeypatch):
    from trace.stages.ground.nodes.author import author_node

    captured = {}

    def _stub_invoke_role(*, role_client, role_name, system_prompt_path, task, context_sections, schema):
        captured["task"] = task
        captured["context_sections"] = context_sections
        return [], {"node_groups": [], "logical_constraints": [], "physical_constraints": []}

    monkeypatch.setattr("trace.stages.ground.nodes.author.invoke_role", _stub_invoke_role)
    state = {
        "intent": "x",
        "evaluation_report": None,
        "escalation_report": {
            "source_stage": "logical",
            "attempt_at_escalation": 2,
            "issues": [{"details": {"issue_kind": "logical.escalation.constraint_conflict", "summary": "A vs B"}}],
            "partial_artifact": {"graph": {"nodes": []}},
        },
    }
    author_node(state, role_client=None)
    assert "escalation_feedback" in captured["context_sections"]
    assert captured["context_sections"]["escalation_feedback"]["source_stage"] == "logical"
    assert "escalation" in captured["task"]


def test_evaluator_node_returns_unsolvable_command_when_artifact_flagged():
    from trace.stages.ground.nodes.evaluator import evaluator_node

    state = {
        "draft_artifact": {
            "node_groups": [],
            "logical_constraints": [],
            "physical_constraints": [],
            "unsolvable": True,
            "unsolvable_reason": "user intent contradicts itself",
        },
        "attempt": 1,
        "max_attempts": 3,
    }
    result = evaluator_node(state, role_client=None)
    assert isinstance(result, Command)
    assert result.goto == END
    assert result.update.get("status") == "unsolvable"
    assert "unsolvable_notes" in result.update
