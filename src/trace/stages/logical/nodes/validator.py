from __future__ import annotations

from langgraph.graph import END
from langgraph.types import Command

from tgraph import TGraph, validate_graph
from tgraph.operations.validate import ValidationContext

from trace.runtime.escalation import build_escalation_report, extract_escalation_issues
from trace.stages.logical.state import LogicalState
from trace.stages.support_files import support_file_path


def validator_node(state: LogicalState) -> Command:
    report = _validate_logical_artifact(state=state, draft=state.get("draft_artifact", {}))
    if report["ok"]:
        return Command(goto="finalize", update={"evaluation_report": report})

    escalation_issues = extract_escalation_issues(report)
    if escalation_issues:
        escalation_payload = build_escalation_report(
            stage_id="logical",
            report=report,
            partial_artifact=state.get("draft_artifact"),
            attempt=state["attempt"],
        )
        return Command(
            goto="escalate",
            update={"evaluation_report": report, "escalation_report": escalation_payload},
        )

    if state["attempt"] >= state["max_attempts"]:
        return Command(
            goto=END,
            update={
                "evaluation_report": report,
                "error": {"message": "logical stage exceeded max attempts", "issues": report["issues"]},
            },
        )
    return Command(goto="repair", update={"evaluation_report": report})


def _validate_logical_artifact(*, state: LogicalState, draft: dict) -> dict:
    constraint_files = _resolve_support_paths(state, draft.get("constraint_files", {}))
    checkpoint_files = _resolve_support_paths(state, draft.get("checkpoint_files", {}))
    return validate_graph(
        TGraph.model_validate(draft["graph"]),
        context=ValidationContext(
            constraint_files=constraint_files,
            checkpoint_files=checkpoint_files,
        ),
    ).model_dump(mode="json")


def _resolve_support_paths(state: LogicalState, refs: dict[str, str]) -> dict[str, str]:
    return {scope: str(support_file_path(state, path)) for scope, path in (refs or {}).items()}
