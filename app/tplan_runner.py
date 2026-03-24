from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.checkpoints import write_checkpoint
from app.stage_runtime import StageRuntime


class RunnerResult(BaseModel):
    run_id: str
    status: str
    stage_history: list[str] = Field(default_factory=list)


class TPlanRunner:
    def __init__(self, stage_runtime: StageRuntime, stage_order: list[str], run_root: str | Path) -> None:
        self.stage_runtime = stage_runtime
        self.stage_order = stage_order
        self.run_root = Path(run_root)

    def run(self, intent: str) -> RunnerResult:
        run_id = uuid4().hex[:8]
        stage_history: list[str] = []
        self.run_root.mkdir(parents=True, exist_ok=True)
        write_checkpoint(
            self.run_root / 'run_start.json',
            {'run_id': run_id, 'intent': intent, 'stage_order': self.stage_order},
        )

        for stage_id in self.stage_order:
            self.stage_runtime.run_stage(stage_id)
            stage_history.append(stage_id)

        self.translate_stub({'run_id': run_id, 'intent': intent})
        write_checkpoint(
            self.run_root / 'run_complete.json',
            {'run_id': run_id, 'status': 'completed', 'stage_history': stage_history},
        )
        return RunnerResult(run_id=run_id, status='completed', stage_history=stage_history)

    def resume(self, run_id: str) -> RunnerResult:
        return RunnerResult(run_id=run_id, status='completed', stage_history=[])

    def translate_stub(self, payload: dict[str, Any]) -> None:
        _ = payload
