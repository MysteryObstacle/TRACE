from __future__ import annotations

from pathlib import Path

from trace.stages.common import invoke_role
from trace.stages.ground.schemas import GroundDraftArtifact
from trace.stages.ground.state import GroundState


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "author.md"


def _report_passed(report) -> bool:
    if report is None:
        return False
    if isinstance(report, dict):
        return bool(report.get("passed", False))
    return bool(getattr(report, "passed", False))


def author_node(state: GroundState, role_client) -> GroundState:
    report = state.get("evaluation_report")
    escalation_report = state.get("escalation_report")
    escalation_mode = bool(escalation_report) and not _report_passed(state.get("evaluation_report"))
    revising = bool(report) and not _report_passed(report) and not escalation_mode
    author_mode = "feedback_revision" if (revising or escalation_mode) else "initial_draft"

    context_sections = {
        "author_mode": author_mode,
        "intent": state["intent"],
    }

    if escalation_mode:
        context_sections["escalation_feedback"] = escalation_report
        task = (
            "Current task mode: `feedback_revision` (escalation).\n"
            "A downstream stage reported issues that may stem from infeasible or conflicting constraints.\n"
            "Re-evaluate `node_groups`, `logical_constraints`, `physical_constraints` against `escalation_feedback.issues`.\n"
            "If the request is genuinely unsatisfiable, set `unsolvable=true` and fill `unsolvable_reason`.\n"
            "Otherwise return a revised complete `GroundDraftArtifact`."
        )
    elif revising:
        context_sections["evaluation_feedback"] = report
        context_sections["evaluation_issues"] = report.get("issues", []) if isinstance(report, dict) else []
        context_sections["evaluation_notes"] = report.get("notes", []) if isinstance(report, dict) else []
        context_sections["previous_artifact"] = state.get("draft_artifact")
        task = (
            "Current task mode: `feedback_revision`.\n"
            "Revise `previous_artifact` according to `evaluation_issues` and `evaluation_notes`. "
            "Return a complete `GroundDraftArtifact`, not a delta patch.\n"
            "Change only the facts called out as wrong, missing, conflicting, or unclear.\n"
            "Preserve unaffected node_groups, logical_constraints, and physical_constraints."
        )
    else:
        task = (
            "Current task mode: `initial_draft`.\n"
            "Generate a complete `GroundDraftArtifact` from `intent`.\n"
            "If the intent gives fixed node ids, CIDRs, link chains, fixed addresses, or node types, preserve those "
            "facts exactly without renaming, merging, or omitting them.\n"
            "If the intent is open-ended, produce a small, reasonable, deployable canonical set of node_groups, "
            "logical_constraints, and physical_constraints.\n"
            "Only create physical_constraints from explicit deployment/image/runtime/flavor/resource requirements or "
            "from functional role nodes that you intentionally introduce for an open-ended archetype."
        )

    messages, artifact = invoke_role(
        role_client=role_client,
        role_name="ground_author",
        system_prompt_path=PROMPT_PATH,
        task=task,
        context_sections=context_sections,
        schema=GroundDraftArtifact,
    )

    return {
        "messages": messages,
        "draft_artifact": artifact,
        "status": "evaluating",
        "events": [{"type": "ground.author.completed", "revision": revising or escalation_mode}],
    }
