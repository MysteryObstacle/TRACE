from __future__ import annotations

from pathlib import Path
from typing import Any

from langgraph.graph import END
from langgraph.types import Command

from trace.stages.common import invoke_role
from trace.stages.ground.schemas import GroundEvaluationReport, structural_issues_from_draft
from trace.stages.ground.state import GroundState


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "evaluator.md"


def evaluator_node(state: GroundState, role_client) -> Command:
    draft = state.get("draft_artifact", {})
    if draft.get("unsolvable"):
        reason = draft.get("unsolvable_reason") or "ground stage marked unsolvable"
        return Command(
            goto=END,
            update={
                "status": "unsolvable",
                "error": {"message": reason, "issues": []},
                "unsolvable_notes": [reason],
                "events": [{"type": "ground.unsolvable", "reason": reason}],
            },
        )

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
    grounding_checks = {
        "attempt": state["attempt"],
        "passed": passed,
        "issue_count": len(merged_issues),
    }
    update: dict[str, Any] = {
        "messages": messages,
        "evaluation_report": report,
        "grounding_checks": grounding_checks,
    }

    if passed:
        return Command(goto="finalize", update=update)

    if state["attempt"] >= state["max_attempts"]:
        update["status"] = "failed"
        update["error"] = {"message": "ground stage exceeded max attempts", "issues": merged_issues}
        return Command(goto=END, update=update)

    update["retry_history"] = [
        {
            "after_attempt": state["attempt"],
            "issues": merged_issues,
            "notes": report.get("notes", []),
        }
    ]
    update["attempt"] = state["attempt"] + 1
    return Command(goto="author", update=update)
