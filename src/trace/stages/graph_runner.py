from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver

from trace.runtime.stage_checkpoint import (
    StageCheckpointConfig,
    latest_stage_checkpoint_id,
    stage_graph_config,
)


@contextmanager
def stage_support_root(
    checkpoint_config: StageCheckpointConfig | None,
    *,
    temp_prefix: str,
) -> Iterator[Path]:
    if checkpoint_config is not None:
        checkpoint_config.support_file_root.mkdir(parents=True, exist_ok=True)
        yield checkpoint_config.support_file_root
        return
    with TemporaryDirectory(prefix=temp_prefix) as support_root:
        yield Path(support_root)


def invoke_stage_graph(
    *,
    build_graph: Callable[[SqliteSaver | None], Any],
    initial_state: dict[str, Any],
    checkpoint_config: StageCheckpointConfig | None,
) -> dict[str, Any]:
    if checkpoint_config is None:
        graph = build_graph(None)
        return graph.invoke(initial_state)

    checkpoint_config.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with SqliteSaver.from_conn_string(str(checkpoint_config.sqlite_path)) as checkpointer:
        graph = build_graph(checkpointer)
        if checkpoint_config.resume:
            checkpoint_id = latest_stage_checkpoint_id(graph, checkpoint_config)
            return graph.invoke(
                None,
                config=stage_graph_config(checkpoint_config, checkpoint_id=checkpoint_id),
            )
        return graph.invoke(
            initial_state,
            config=stage_graph_config(checkpoint_config),
        )
