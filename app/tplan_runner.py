from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

import orjson
from pydantic import BaseModel, Field

from agent.langchain.tracing import TraceRecorder
from app.checkpoints import write_checkpoint
from app.progress import ProgressReporter
from app.stage_runtime import StageRuntime
from artifacts.store import ArtifactStore


class RunnerResult(BaseModel):
    run_id: str
    status: str
    session_root: str = ''
    stage_history: list[str] = Field(default_factory=list)
    validation_attempts: dict[str, int] = Field(default_factory=dict)


class SessionLayout(str, Enum):
    DIRECT = 'direct'
    SESSIONED = 'sessioned'


class TPlanRunner:
    def __init__(
        self,
        stage_runtime: StageRuntime,
        stage_order: list[str],
        run_root: str | Path,
        tracer: TraceRecorder | None = None,
        session_layout: SessionLayout | str = SessionLayout.DIRECT,
        reporter: ProgressReporter | None = None,
    ) -> None:
        self.stage_runtime = stage_runtime
        self.stage_order = stage_order
        self.run_root = Path(run_root)
        self.tracer = tracer or TraceRecorder(enabled=False)
        self.session_layout = SessionLayout(session_layout)
        self.reporter = reporter or ProgressReporter()

    def run(self, intent: str) -> RunnerResult:
        run_id = uuid4().hex[:8]
        session_root = self._session_root(run_id)
        stage_history: list[str] = []
        validation_attempts: dict[str, int] = {}
        session_root.mkdir(parents=True, exist_ok=True)
        artifact_store = ArtifactStore(session_root)
        self.stage_runtime.bind_artifact_store(artifact_store)
        artifact_store.write('runtime', 'intent', intent)
        self.reporter.run_started(run_id, session_root, intent)
        write_checkpoint(
            session_root / 'run_start.json',
            {'run_id': run_id, 'intent': intent, 'stage_order': self.stage_order},
        )

        current_stage: str | None = None
        try:
            with self.tracer.root_run(run_id=run_id, intent=intent, session_root=session_root):
                for stage_id in self.stage_order:
                    current_stage = stage_id
                    self.reporter.stage_started(stage_id)
                    result = self.stage_runtime.run_stage(stage_id)
                    stage_history.append(stage_id)
                    validation_attempts[stage_id] = result.attempts
                    self.reporter.stage_completed(stage_id, result.attempts)
        except Exception as exc:
            write_checkpoint(
                session_root / 'state.json',
                {
                    'run_id': run_id,
                    'status': 'failed',
                    'session_root': str(session_root),
                    'current_stage': current_stage,
                    'stage_history': stage_history,
                    'validation_attempts': validation_attempts,
                },
            )
            self.reporter.run_failed(run_id, session_root, current_stage, str(exc))
            raise

        self.translate_stub({'run_id': run_id, 'intent': intent})
        write_checkpoint(
            session_root / 'state.json',
            {
                'run_id': run_id,
                'status': 'completed',
                'session_root': str(session_root),
                'stage_history': stage_history,
                'validation_attempts': validation_attempts,
            },
        )
        self.reporter.run_completed(run_id, session_root)
        return RunnerResult(
            run_id=run_id,
            status='completed',
            session_root=str(session_root),
            stage_history=stage_history,
            validation_attempts=validation_attempts,
        )

    def resume(self, run_id: str) -> RunnerResult:
        state_path = self._session_root(run_id) / 'state.json'
        if not state_path.exists():
            return RunnerResult(run_id=run_id, status='completed', session_root=str(self._session_root(run_id)), stage_history=[], validation_attempts={})

        payload = orjson.loads(state_path.read_bytes())
        return RunnerResult(
            run_id=payload['run_id'],
            status=payload['status'],
            session_root=payload.get('session_root', str(state_path.parent)),
            stage_history=payload.get('stage_history', []),
            validation_attempts=payload.get('validation_attempts', {}),
        )

    def translate_stub(self, payload: dict[str, Any]) -> None:
        _ = payload

    def _session_root(self, run_id: str) -> Path:
        if self.session_layout == SessionLayout.SESSIONED:
            return self.run_root / run_id
        return self.run_root
