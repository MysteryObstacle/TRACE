from __future__ import annotations

from pathlib import Path

from trace.stages.common import invoke_role
from trace.stages.ground.schemas import GroundEvaluationReport
from trace.stages.ground.state import GroundState


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "evaluator.md"


def evaluator_node(state: GroundState, role_client) -> GroundState:
    messages, raw_report = invoke_role(
        role_client=role_client,
        role_name="ground_evaluator",
        system_prompt_path=PROMPT_PATH,
        task="Evaluate the ground-stage artifact and decide whether it is ready.",
        context_sections={"artifact": state["draft_artifact"]},
        schema=GroundEvaluationReport,
    )
    report = GroundEvaluationReport.model_validate(raw_report).model_dump(mode="json")
    state["messages"] = messages
    state["evaluation_report"] = report
    state["grounding_checks"] = {
        "attempt": state["attempt"],
        "passed": bool(report.get("passed")),
        "issue_count": len(report.get("issues", [])),
    }
    if report["passed"]:
        state["next_action"] = "finalize"
        return state
    if state["attempt"] >= state["max_attempts"]:
        state["status"] = "failed"
        state["error"] = {"message": "ground stage exceeded max attempts", "issues": report["issues"]}
        state["next_action"] = "failed"
        return state
    state["retry_history"] = [
        *state.get("retry_history", []),
        {
            "after_attempt": state["attempt"],
            "issues": report["issues"],
            "optimizer_brief": report.get("optimizer_brief", {}),
        },
    ]
    state["attempt"] += 1
    state["next_action"] = "author"
    return state
