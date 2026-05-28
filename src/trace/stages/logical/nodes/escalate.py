from __future__ import annotations

from trace.stages.logical.state import LogicalState
from trace.stages.stage_results import escalated_stage_result


def escalate_node(state: LogicalState) -> dict[str, object]:
    return escalated_stage_result(stage_id="logical", state=state)
