from __future__ import annotations

from trace.stages.logical.state import LogicalState
from trace.tools.tgraph.runtime import TGraphRuntime
from trace.tools.tgraph.validate import run_default_validators


def validator_node(state: LogicalState) -> LogicalState:
    authored_checkpoints = state.get("draft_artifact", {}).get("logical_checkpoints")
    if authored_checkpoints is None:
        authored_checkpoints = state.get("author_output", {}).get("logical_checkpoints", [])
    authored_script = state.get("draft_artifact", {}).get("logical_validator_script")
    if authored_script is None:
        authored_script = state.get("author_output", {}).get("logical_validator_script")

    report = run_default_validators(
        TGraphRuntime.from_json(state["draft_artifact"]["tgraph_logical"]).to_json(),
        logical_constraints=state.get("ground_artifact", {}).get("logical_constraints", []),
        logical_checkpoints=authored_checkpoints,
        logical_validator_script=authored_script,
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
