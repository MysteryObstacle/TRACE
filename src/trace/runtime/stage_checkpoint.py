from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StageCheckpointConfig:
    run_id: str
    stage_id: str
    sqlite_path: Path
    support_file_root: Path
    resume: bool = False

    @property
    def thread_id(self) -> str:
        return f"{self.run_id}:{self.stage_id}"


class StageCheckpointUnavailable(ValueError):
    pass


def stage_graph_config(config: StageCheckpointConfig, *, checkpoint_id: str | None = None) -> dict[str, Any]:
    configurable = {"thread_id": config.thread_id}
    if checkpoint_id is not None:
        configurable["checkpoint_id"] = checkpoint_id
    return {"configurable": configurable}


def latest_stage_checkpoint_id(graph: Any, config: StageCheckpointConfig) -> str:
    try:
        history = list(graph.get_state_history(stage_graph_config(config)))
    except Exception as exc:  # noqa: BLE001
        raise StageCheckpointUnavailable(
            f"stage sqlite checkpoint for {config.stage_id!r} is not readable in {config.run_id!r}: {exc}"
        ) from exc
    for snapshot in history:
        values = snapshot.values if isinstance(snapshot.values, dict) else {}
        if values:
            checkpoint_id = snapshot.config["configurable"].get("checkpoint_id")
            if checkpoint_id:
                return str(checkpoint_id)
    raise StageCheckpointUnavailable(
        f"stage sqlite checkpoint for {config.stage_id!r} not found in {config.run_id!r}"
    )
