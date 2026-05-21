from __future__ import annotations

from langgraph.graph import END, StateGraph

from trace.config.settings import TraceSettings
from trace.stages.common import require_stage_result
from trace.stages.ground.nodes.author import author_node
from trace.stages.ground.nodes.evaluator import evaluator_node
from trace.stages.ground.nodes.finalize import finalize_node
from trace.stages.ground.nodes.prepare import prepare_node
from trace.stages.ground.state import GroundState


def run_ground_stage(*, intent: str, role_client, settings: TraceSettings) -> dict[str, Any]:
    graph = _build_ground_graph(role_client=role_client, settings=settings)
    initial: GroundState = {
        "intent": intent,
        "attempt": 1,
        "max_attempts": settings.roles["ground_evaluator"].max_attempts,
        "status": "preparing",
        "retry_history": [],
        "events": [],
    }
    final_state = graph.invoke(initial)
    return require_stage_result(stage_id="ground", final_state=final_state)


def _build_ground_graph(*, role_client, settings: TraceSettings):
    del settings
    graph = StateGraph(GroundState)
    graph.add_node("prepare", prepare_node)
    graph.add_node("author", lambda state: author_node(state, role_client))
    graph.add_node("evaluator", lambda state: evaluator_node(state, role_client))
    graph.add_node("finalize", finalize_node)
    graph.set_entry_point("prepare")
    graph.add_edge("prepare", "author")
    graph.add_edge("author", "evaluator")
    graph.add_conditional_edges(
        "evaluator",
        lambda state: state["next_action"],
        {
            "finalize": "finalize",
            "author": "author",
            "failed": END,
        },
    )
    graph.add_edge("finalize", END)
    return graph.compile()


__all__ = ["run_ground_stage"]
