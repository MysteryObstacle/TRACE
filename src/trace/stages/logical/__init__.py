from __future__ import annotations

from tempfile import TemporaryDirectory
from typing import Any

from langgraph.graph import END, StateGraph

from trace.config.settings import TraceSettings
from trace.stages.common import require_stage_result
from trace.stages.logical.nodes.author import author_node
from trace.stages.logical.nodes.builder import builder_node
from trace.stages.logical.nodes.escalate import escalate_node
from trace.stages.logical.nodes.finalize import finalize_node
from trace.stages.logical.nodes.prepare import prepare_node
from trace.stages.logical.nodes.repair import repair_node
from trace.stages.logical.nodes.validator import validator_node
from trace.stages.logical.state import LogicalState


def run_logical_stage(
    *,
    ground_artifact: dict[str, Any],
    role_client,
    settings: TraceSettings,
    inherited_support_files: dict[str, str] | None = None,
) -> dict[str, Any]:
    graph = _build_logical_graph(role_client=role_client, settings=settings)
    with TemporaryDirectory(prefix="trace-logical-") as support_root:
        initial: LogicalState = {
            "ground_artifact": ground_artifact,
            "attempt": 1,
            "max_attempts": settings.roles["logical_repair"].max_attempts,
            "repair_history": [],
            "events": [],
            "support_files": dict(inherited_support_files or {}),
            "support_file_root": support_root,
        }
        final_state = graph.invoke(initial)
    return require_stage_result(stage_id="logical", final_state=final_state)


def _build_logical_graph(*, role_client, settings: TraceSettings):
    del settings
    graph = StateGraph(LogicalState)
    graph.add_node("prepare", prepare_node)
    graph.add_node("author", lambda state: author_node(state, role_client))
    graph.add_node("builder", lambda state: builder_node(state, role_client))
    graph.add_node("validator", validator_node)
    graph.add_node("repair", lambda state: repair_node(state, role_client))
    graph.add_node("finalize", finalize_node)
    graph.add_node("escalate", escalate_node)
    graph.set_entry_point("prepare")
    graph.add_edge("prepare", "author")
    graph.add_edge("author", "builder")
    graph.add_edge("builder", "validator")
    graph.add_edge("repair", "validator")
    graph.add_edge("finalize", END)
    graph.add_edge("escalate", END)
    return graph.compile()


__all__ = ["run_logical_stage"]
