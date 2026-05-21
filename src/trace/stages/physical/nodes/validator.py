from __future__ import annotations

from trace.stages.physical.state import PhysicalState
from trace.tools.tgraph.runtime import TGraphRuntime
from trace.tools.tgraph.validate import run_default_validators


def validator_node(state: PhysicalState) -> PhysicalState:
    report = _validate_physical_artifact(
        artifact=state["draft_artifact"],
        logical_graph=state["logical_artifact"]["tgraph_logical"],
        author_output=state.get("author_output", {}),
        physical_constraints=state.get("ground_artifact", {}).get("physical_constraints", []),
    )
    state["evaluation_report"] = report
    if report["ok"]:
        state["next_action"] = "finalize"
        return state
    if state["attempt"] >= state["max_attempts"]:
        state["error"] = {"message": "physical stage exceeded max attempts", "issues": report["issues"]}
        state["next_action"] = "failed"
        return state
    state["next_action"] = "repair"
    return state


def _validate_physical_artifact(
    *,
    artifact: dict,
    logical_graph: dict,
    author_output: dict,
    physical_constraints: list[dict] | None = None,
) -> dict:
    logical_graph_json = TGraphRuntime.from_json(logical_graph).to_json()
    physical_graph_json = TGraphRuntime.from_json(artifact["tgraph_physical"]).to_json()
    authored_checkpoints = artifact.get("physical_checkpoints")
    if authored_checkpoints is None:
        authored_checkpoints = author_output.get("physical_checkpoints", [])
    authored_script = artifact.get("physical_validator_script")
    if authored_script is None:
        authored_script = author_output.get("physical_validator_script")
    report = run_default_validators(
        physical_graph_json,
        physical_constraints=physical_constraints or [],
        physical_checkpoints=authored_checkpoints,
        physical_validator_script=authored_script,
    ).model_dump(mode="json")
    issues = list(report["issues"])
    logical_link_ids = sorted(link["id"] for link in logical_graph_json.get("links", []))
    physical_link_ids = sorted(link["id"] for link in physical_graph_json.get("links", []))
    if physical_link_ids != logical_link_ids:
        issues.append(
            {
                "code": "physical_links_changed",
                "message": "physical graph must preserve logical links",
                "severity": "error",
                "targets": [],
                "json_paths": ["$.links"],
                "provenance": {"layer": "f3", "source": "builtin"},
            }
        )
    logical_node_ids = sorted(node["id"] for node in logical_graph_json.get("nodes", []))
    physical_node_ids = sorted(node["id"] for node in physical_graph_json.get("nodes", []))
    if physical_node_ids != logical_node_ids:
        issues.append(
            {
                "code": "physical_node_ids_changed",
                "message": "physical graph must preserve logical node identities",
                "severity": "error",
                "targets": [],
                "json_paths": ["$.nodes"],
                "provenance": {"layer": "f3", "source": "builtin"},
            }
        )
    return {"ok": not any(item["severity"] == "error" for item in issues), "issues": issues}
