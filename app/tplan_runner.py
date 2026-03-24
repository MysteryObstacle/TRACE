from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import orjson
from pydantic import BaseModel, Field

from agent.langchain.tracing import TraceRecorder
from app.checkpoints import write_checkpoint
from app.stage_runtime import StageRuntime


class RunnerResult(BaseModel):
    run_id: str
    status: str
    stage_history: list[str] = Field(default_factory=list)
    validation_attempts: dict[str, int] = Field(default_factory=dict)


class TPlanRunner:
    def __init__(
        self,
        stage_runtime: StageRuntime,
        stage_order: list[str],
        run_root: str | Path,
        tracer: TraceRecorder | None = None,
    ) -> None:
        self.stage_runtime = stage_runtime
        self.stage_order = stage_order
        self.run_root = Path(run_root)
        self.tracer = tracer or TraceRecorder(enabled=False)

    def run(self, intent: str) -> RunnerResult:
        run_id = uuid4().hex[:8]
        stage_history: list[str] = []
        validation_attempts: dict[str, int] = {}
        self.run_root.mkdir(parents=True, exist_ok=True)
        write_checkpoint(
            self.run_root / 'run_start.json',
            {'run_id': run_id, 'intent': intent, 'stage_order': self.stage_order},
        )

        with self.tracer.root_run(run_id=run_id):
            for stage_id in self.stage_order:
                result = self.stage_runtime.run_stage(stage_id)
                stage_history.append(stage_id)
                validation_attempts[stage_id] = result.attempts

        self.translate_stub({'run_id': run_id, 'intent': intent})
        write_checkpoint(
            self.run_root / 'state.json',
            {
                'run_id': run_id,
                'status': 'completed',
                'stage_history': stage_history,
                'validation_attempts': validation_attempts,
            },
        )
        return RunnerResult(
            run_id=run_id,
            status='completed',
            stage_history=stage_history,
            validation_attempts=validation_attempts,
        )

    def resume(self, run_id: str) -> RunnerResult:
        state_path = self.run_root / 'state.json'
        if not state_path.exists():
            return RunnerResult(run_id=run_id, status='completed', stage_history=[], validation_attempts={})

        payload = orjson.loads(state_path.read_bytes())
        return RunnerResult(
            run_id=payload['run_id'],
            status=payload['status'],
            stage_history=payload.get('stage_history', []),
            validation_attempts=payload.get('validation_attempts', {}),
        )

    def translate_stub(self, payload: dict[str, Any]) -> None:
        _ = payload
