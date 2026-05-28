from __future__ import annotations

from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from trace.config.settings import TraceSettings
from trace.runtime.stage_checkpoint import StageCheckpointConfig
from trace.stages.common import require_stage_result
from trace.stages.graph_runner import invoke_stage_graph, stage_support_root
from trace.stages.ground.nodes.author import author_node
from trace.stages.ground.nodes.evaluator import evaluator_node
from trace.stages.ground.nodes.finalize import finalize_node
from trace.stages.ground.nodes.prepare import prepare_node
from trace.stages.ground.state import GroundState


def run_ground_stage(
    *,
    intent: str,
    role_client,
    settings: TraceSettings,
    escalation_report: dict[str, Any] | None = None,
    checkpoint_config: StageCheckpointConfig | None = None,
) -> dict[str, Any]:
    with stage_support_root(checkpoint_config, temp_prefix="trace-ground-") as support_root:
        initial: GroundState = {
            "intent": intent,
            "attempt": 1,
            "max_attempts": settings.roles["ground_evaluator"].max_attempts,
            "status": "preparing",
            "retry_history": [],
            "events": [],
            "support_files": {},
            "support_file_root": str(support_root),
            "escalation_report": escalation_report,
        }
        final_state = invoke_stage_graph(
            build_graph=lambda checkpointer: _build_ground_graph(
                role_client=role_client,
                settings=settings,
                checkpointer=checkpointer,
            ),
            initial_state=initial,
            checkpoint_config=checkpoint_config,
        )
    return require_stage_result(stage_id="ground", final_state=final_state)


def _build_ground_graph(*, role_client, settings: TraceSettings, checkpointer: SqliteSaver | None = None):
    del settings
    graph = StateGraph(GroundState)
    graph.add_node("prepare", prepare_node)
    graph.add_node("author", lambda state: author_node(state, role_client))
    graph.add_node("evaluator", lambda state: evaluator_node(state, role_client))
    graph.add_node("finalize", finalize_node)
    graph.set_entry_point("prepare")
    graph.add_edge("prepare", "author")
    graph.add_edge("author", "evaluator")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)


__all__ = ["run_ground_stage"]
