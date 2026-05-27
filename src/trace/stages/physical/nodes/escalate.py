from __future__ import annotations

from trace.stages.physical.state import PhysicalState


def escalate_node(state: PhysicalState) -> dict[str, object]:
    prior_events = list(state.get("events", []))
    event = {"type": "physical.escalated", "attempt": state.get("attempt", 1)}
    return {
        "result": {
            "status": "escalated",
            "stage_id": "physical",
            "escalation_report": state.get("escalation_report"),
            "partial_artifact": state.get("draft_artifact"),
            "evaluation_summary": state.get("evaluation_report"),
            "attempts_used": state.get("attempt", 1),
            "messages": state.get("messages", []),
            "tool_journal": [],
            "repair_history": list(state.get("repair_history", [])),
            "events": [*prior_events, event],
            "support_files": state.get("support_files", {}),
        },
        "events": [event],
    }
