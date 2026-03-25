from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from langsmith import Client, tracing_context
from langsmith.run_helpers import get_current_run_tree, trace


@dataclass
class TraceRecorder:
    enabled: bool = False
    project_name: str | None = None
    client: Client | Any | None = None

    def _normalize_payload(self, payload: dict[str, object]) -> dict[str, object]:
        normalized: dict[str, object] = {}
        for key, value in payload.items():
            if value is None:
                continue
            normalized[key] = self._normalize_value(value)
        return normalized

    def _normalize_value(self, value: object) -> object:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [self._normalize_value(item) for item in value]
        if isinstance(value, tuple):
            return [self._normalize_value(item) for item in value]
        if isinstance(value, dict):
            return {str(key): self._normalize_value(item) for key, item in value.items()}
        return str(value)

    @contextmanager
    def _span(
        self,
        *,
        name: str,
        run_type: str,
        inputs: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
        tags: list[str] | None = None,
    ) -> Iterator[None]:
        if not self.enabled:
            yield
            return

        with trace(
            name=name,
            run_type=run_type,
            inputs=self._normalize_payload(inputs or {}),
            metadata=self._normalize_payload(metadata or {}),
            tags=tags,
            client=self.client,
            project_name=self.project_name,
            parent=get_current_run_tree(),
        ):
            yield

    @contextmanager
    def root_run(self, **kwargs: object) -> Iterator[None]:
        if not self.enabled:
            yield
            return

        metadata = self._normalize_payload({'kind': 'root_run', **kwargs})
        with tracing_context(
            enabled=True,
            project_name=self.project_name,
            client=self.client,
            metadata=metadata,
            tags=['trace-iac', 'root'],
        ):
            with self._span(
                name='trace.run',
                run_type='chain',
                inputs=kwargs,
                metadata=metadata,
                tags=['trace-iac', 'root'],
            ):
                yield

    @contextmanager
    def stage_run(self, **kwargs: object) -> Iterator[None]:
        stage_id = str(kwargs.get('stage_id', 'unknown'))
        with self._span(
            name=f'stage.{stage_id}',
            run_type='chain',
            inputs=kwargs,
            metadata={'kind': 'stage_run', **kwargs},
            tags=['trace-iac', 'stage', f'stage:{stage_id}'],
        ):
            yield

    @contextmanager
    def validation_run(self, **kwargs: object) -> Iterator[None]:
        stage_id = str(kwargs.get('stage_id', 'unknown'))
        with self._span(
            name=f'validation.{stage_id}',
            run_type='tool',
            inputs=kwargs,
            metadata={'kind': 'validation_run', **kwargs},
            tags=['trace-iac', 'validation', f'stage:{stage_id}'],
        ):
            yield

    @contextmanager
    def patch_run(self, **kwargs: object) -> Iterator[None]:
        stage_id = str(kwargs.get('stage_id', 'unknown'))
        with self._span(
            name=f'patch.{stage_id}',
            run_type='tool',
            inputs=kwargs,
            metadata={'kind': 'patch_run', **kwargs},
            tags=['trace-iac', 'patch', f'stage:{stage_id}'],
        ):
            yield

    @contextmanager
    def agent_run(self, **kwargs: object) -> Iterator[None]:
        stage_id = str(kwargs.get('stage_id', 'unknown'))
        with self._span(
            name=f'agent.{stage_id}',
            run_type='chain',
            inputs=kwargs,
            metadata={'kind': 'agent_run', **kwargs},
            tags=['trace-iac', 'agent', f'stage:{stage_id}'],
        ):
            yield
