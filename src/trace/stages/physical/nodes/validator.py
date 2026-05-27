from __future__ import annotations

from langgraph.graph import END
from langgraph.types import Command

from tgraph import TGraph, validate_graph
from tgraph.operations.validate import ValidationContext

from trace.runtime.escalation import build_escalation_report, extract_escalation_issues
from trace.stages.physical.state import PhysicalState
from trace.stages.support_files import support_file_path


def validator_node(state: PhysicalState) -> Command:
    report = _validate_physical_artifact(
        artifact=state["draft_artifact"],
        logical_graph=state["logical_artifact"]["graph"],
        state=state,
    )
    if report["ok"]:
        return Command(goto="finalize", update={"evaluation_report": report})

    escalation_issues = extract_escalation_issues(report)
    if escalation_issues:
        escalation_payload = build_escalation_report(
            stage_id="physical",
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
                "error": {"message": "physical stage exceeded max attempts", "issues": report["issues"]},
            },
        )
    return Command(goto="repair", update={"evaluation_report": report})


def _validate_physical_artifact(
    *,
    artifact: dict,
    logical_graph: dict,
    state: PhysicalState,
) -> dict:
    logical_graph_model = TGraph.model_validate(logical_graph)
    physical_graph_model = TGraph.model_validate(artifact["graph"])
    constraint_files = _resolve_support_paths(state, artifact.get("constraint_files", {}))
    checkpoint_files = _resolve_support_paths(state, artifact.get("checkpoint_files", {}))
    return validate_graph(
        physical_graph_model,
        context=ValidationContext(
            preserve_topology_from=logical_graph_model,
            required_node_fields=["image", "flavor"],
            constraint_files=constraint_files,
            checkpoint_files=checkpoint_files,
            references={"logical": logical_graph_model},
        ),
    ).model_dump(mode="json")


def _resolve_support_paths(state: PhysicalState, refs: dict[str, str]) -> dict[str, str]:
    return {scope: str(support_file_path(state, path)) for scope, path in (refs or {}).items()}
