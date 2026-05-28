from __future__ import annotations

from trace.stages.physical.state import PhysicalState
from trace.stages.stage_results import escalated_stage_result


def escalate_node(state: PhysicalState) -> dict[str, object]:
    return escalated_stage_result(stage_id="physical", state=state)
