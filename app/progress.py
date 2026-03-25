from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


class ProgressReporter:
    def run_started(self, run_id: str, session_root: Path, intent: str) -> None:
        _ = (run_id, session_root, intent)

    def stage_started(self, stage_id: str) -> None:
        _ = stage_id

    def stage_completed(self, stage_id: str, attempts: int) -> None:
        _ = (stage_id, attempts)

    def repair_round(self, stage_id: str, attempt: int, max_rounds: int) -> None:
        _ = (stage_id, attempt, max_rounds)

    def run_completed(self, run_id: str, session_root: Path) -> None:
        _ = (run_id, session_root)

    def run_failed(self, run_id: str, session_root: Path, stage_id: str | None, error: str) -> None:
        _ = (run_id, session_root, stage_id, error)

    def llm_stream_started(self, stage_id: str, runtime_mode: str | None) -> None:
        _ = (stage_id, runtime_mode)

    def llm_stream_chunk(self, stage_id: str, text: str) -> None:
        _ = (stage_id, text)

    def llm_stream_completed(self, stage_id: str) -> None:
        _ = stage_id


@dataclass
class ConsoleProgressReporter(ProgressReporter):
    enabled: bool = False
    stream_enabled: bool = False
    printer: Callable[[str], None] = field(default_factory=lambda: (lambda message: print(message, flush=True)))
    stream_writer: Callable[[str], None] = field(default_factory=lambda: (lambda text: print(text, end='', flush=True)))

    def _emit(self, message: str) -> None:
        if self.enabled:
            self.printer(message)

    def _emit_stream(self, text: str) -> None:
        if self.stream_enabled:
            self.stream_writer(text)

    def run_started(self, run_id: str, session_root: Path, intent: str) -> None:
        _ = intent
        self._emit(f'session:{run_id}')
        self._emit(f'artifacts:{session_root}')

    def stage_started(self, stage_id: str) -> None:
        self._emit(f'stage:{stage_id}:started')

    def stage_completed(self, stage_id: str, attempts: int) -> None:
        self._emit(f'stage:{stage_id}:completed attempts={attempts}')

    def repair_round(self, stage_id: str, attempt: int, max_rounds: int) -> None:
        self._emit(f'stage:{stage_id}:repair {attempt}/{max_rounds}')

    def run_completed(self, run_id: str, session_root: Path) -> None:
        _ = (run_id, session_root)

    def run_failed(self, run_id: str, session_root: Path, stage_id: str | None, error: str) -> None:
        stage_label = stage_id or 'unknown'
        self._emit(f'failed:{run_id}:stage={stage_label}')
        self._emit(f'error:{error}')
        self._emit(f'artifacts:{session_root}')

    def llm_stream_started(self, stage_id: str, runtime_mode: str | None) -> None:
        if not self.stream_enabled:
            return
        suffix = f' mode={runtime_mode}' if runtime_mode else ''
        self.printer(f'llm:{stage_id}:start{suffix}')

    def llm_stream_chunk(self, stage_id: str, text: str) -> None:
        _ = stage_id
        self._emit_stream(text)

    def llm_stream_completed(self, stage_id: str) -> None:
        if not self.stream_enabled:
            return
        self.stream_writer('\n')
        self.printer(f'llm:{stage_id}:end')
