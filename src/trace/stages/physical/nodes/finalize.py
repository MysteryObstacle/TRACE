from __future__ import annotations

from trace.stages.physical.schemas import PhysicalArtifact
from trace.stages.physical.state import PhysicalState
from trace.stages.stage_results import completed_stage_result


def finalize_node(state: PhysicalState) -> PhysicalState:
    artifact = PhysicalArtifact.model_validate(state["draft_artifact"]).model_dump(mode="json")
    return completed_stage_result(stage_id="physical", state=state, artifact=artifact)
