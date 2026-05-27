from __future__ import annotations

from tgraph import TGraph, validate_graph
from tgraph.operations.validate import ValidationContext

from trace.stages.logical.state import LogicalState
from trace.stages.support_files import support_file_path


def validator_node(state: LogicalState) -> LogicalState:
    draft = state.get("draft_artifact", {})
    constraint_files = _resolve_support_paths(state, draft.get("constraint_files", {}))
    checkpoint_files = _resolve_support_paths(state, draft.get("checkpoint_files", {}))

    report = validate_graph(
        TGraph.model_validate(state["draft_artifact"]["graph"]),
        context=ValidationContext(
            constraint_files=constraint_files,
            checkpoint_files=checkpoint_files,
        ),
    ).model_dump(mode="json")
    state["evaluation_report"] = report
    if report["ok"]:
        state["next_action"] = "finalize"
        return state
    if state["attempt"] >= state["max_attempts"]:
        state["error"] = {"message": "logical stage exceeded max attempts", "issues": report["issues"]}
        state["next_action"] = "failed"
        return state
    state["next_action"] = "repair"
    return state


def _resolve_support_paths(state: LogicalState, refs: dict[str, str]) -> dict[str, str]:
    return {scope: str(support_file_path(state, path)) for scope, path in (refs or {}).items()}
