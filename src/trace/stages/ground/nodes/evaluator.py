from __future__ import annotations

from pathlib import Path
from typing import Any

from trace.stages.common import invoke_role
from trace.stages.ground.schemas import GroundEvaluationReport, GroundIssue, structural_issues_from_draft
from trace.stages.ground.state import GroundState


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "evaluator.md"


def evaluator_node(state: GroundState, role_client) -> GroundState:
    draft = state.get("draft_artifact", {})
    structural_issues = structural_issues_from_draft(draft)

    messages, raw_report = invoke_role(
        role_client=role_client,
        role_name="ground_evaluator",
        system_prompt_path=PROMPT_PATH,
        task=(
            "Evaluate the ground-stage draft artifact for semantic completeness only. "
            "Structural constraint-file issues are already provided separately; do not re-check kinds or JSON shape."
        ),
        context_sections={
            "artifact": draft,
            "structural_issues": structural_issues,
        },
        schema=GroundEvaluationReport,
    )
    semantic_report = GroundEvaluationReport.model_validate(raw_report).model_dump(mode="json")
    merged_issues = [*structural_issues, *semantic_report.get("issues", [])]
    passed = bool(semantic_report.get("passed")) and not merged_issues

    report = {
        "passed": passed,
        "issues": merged_issues,
        "notes": semantic_report.get("notes", []),
    }

    state["messages"] = messages
    state["evaluation_report"] = report
    state["grounding_checks"] = {
        "attempt": state["attempt"],
        "passed": passed,
        "issue_count": len(merged_issues),
    }

    if passed:
        state["next_action"] = "finalize"
        return state

    if state["attempt"] >= state["max_attempts"]:
        state["status"] = "failed"
        state["error"] = {"message": "ground stage exceeded max attempts", "issues": merged_issues}
        state["next_action"] = "failed"
        return state

    state["retry_history"] = [
        *state.get("retry_history", []),
        {
            "after_attempt": state["attempt"],
            "issues": merged_issues,
            "notes": report.get("notes", []),
        },
    ]
    state["attempt"] += 1
    state["next_action"] = "author"
    return state
