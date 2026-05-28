from __future__ import annotations

from trace.stages.logical.schemas import LogicalArtifact
from trace.stages.logical.state import LogicalState
from trace.stages.stage_results import completed_stage_result


def finalize_node(state: LogicalState) -> LogicalState:
    artifact = LogicalArtifact.model_validate(state["draft_artifact"]).model_dump(mode="json")
    return completed_stage_result(stage_id="logical", state=state, artifact=artifact)
