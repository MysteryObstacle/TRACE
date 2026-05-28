from __future__ import annotations

from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver

from trace.config.settings import TraceSettings
from trace.runtime.stage_checkpoint import StageCheckpointConfig
from trace.stages.common import require_stage_result
from trace.stages.graph_runner import invoke_stage_graph, stage_support_root
from trace.stages.stage_results import compile_repair_stage_graph
from trace.stages.physical.nodes.author import author_node
from trace.stages.physical.nodes.builder import builder_node
from trace.stages.physical.nodes.escalate import escalate_node
from trace.stages.physical.nodes.finalize import finalize_node
from trace.stages.physical.nodes.prepare import prepare_node
from trace.stages.physical.nodes.repair import repair_node
from trace.stages.physical.nodes.validator import validator_node
from trace.stages.physical.state import PhysicalState


def run_physical_stage(
    *,
    logical_artifact: dict[str, Any],
    ground_artifact: dict[str, Any],
    role_client,
    settings: TraceSettings,
    inherited_support_files: dict[str, str] | None = None,
    checkpoint_config: StageCheckpointConfig | None = None,
) -> dict[str, Any]:
    with stage_support_root(checkpoint_config, temp_prefix="trace-physical-") as support_root:
        initial: PhysicalState = {
            "logical_artifact": logical_artifact,
            "ground_artifact": ground_artifact,
            "attempt": 1,
            "max_attempts": settings.roles["physical_repair"].max_attempts,
            "repair_history": [],
            "events": [],
            "support_files": dict(inherited_support_files or {}),
            "support_file_root": str(support_root),
        }
        final_state = invoke_stage_graph(
            build_graph=lambda checkpointer: _build_physical_graph(
                role_client=role_client,
                settings=settings,
                checkpointer=checkpointer,
            ),
            initial_state=initial,
            checkpoint_config=checkpoint_config,
        )
    return require_stage_result(stage_id="physical", final_state=final_state)


def _build_physical_graph(*, role_client, settings: TraceSettings, checkpointer: SqliteSaver | None = None):
    del settings
    return compile_repair_stage_graph(
        PhysicalState,
        nodes={
            "prepare": prepare_node,
            "author": lambda state: author_node(state, role_client),
            "builder": lambda state: builder_node(state, role_client),
            "validator": validator_node,
            "repair": lambda state: repair_node(state, role_client),
            "finalize": finalize_node,
            "escalate": escalate_node,
        },
        checkpointer=checkpointer,
    )


__all__ = ["run_physical_stage"]
