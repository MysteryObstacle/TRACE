from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from langsmith import Client, tracing_context
from langsmith.run_helpers import get_current_run_tree, trace

from trace.config.settings import LangSmithSettings


@dataclass
class SpanHandle:
    run: Any | None = None

    def end(self, outputs: dict[str, Any] | None = None) -> None:
        if self.run is None or not hasattr(self.run, "end"):
            return
        self.run.end(outputs=outputs or {})


class TraceObserver:
    def __init__(self, settings: LangSmithSettings) -> None:
        self.settings = settings
        self.client = None
        if settings.enabled:
            self.client = Client(api_key=settings.api_key, api_url=settings.endpoint)

    @contextmanager
    def root_run(self, **inputs: Any) -> Iterator[SpanHandle]:
        if not self.settings.enabled:
            yield SpanHandle()
            return
        with tracing_context(
            enabled=True,
            project_name=self.settings.project,
            client=self.client,
            metadata={"kind": "run"},
            tags=["trace", "run"],
        ):
            with trace(
                name="trace.run",
                run_type="chain",
                inputs=inputs,
                client=self.client,
                project_name=self.settings.project,
                parent=get_current_run_tree(),
            ) as run:
                yield SpanHandle(run)

    @contextmanager
    def stage_run(self, stage_id: str, **inputs: Any) -> Iterator[SpanHandle]:
        with self._span(f"stage.{stage_id}", ["trace", "stage", f"stage:{stage_id}"], **inputs) as handle:
            yield handle

    @contextmanager
    def role_run(self, role_name: str, **inputs: Any) -> Iterator[SpanHandle]:
        with self._span(f"role.{role_name}", ["trace", "role", f"role:{role_name}"], **inputs) as handle:
            yield handle

    @contextmanager
    def tool_run(self, tool_name: str, **inputs: Any) -> Iterator[SpanHandle]:
        with self._span(f"tool.{tool_name}", ["trace", "tool", f"tool:{tool_name}"], **inputs) as handle:
            yield handle

    @contextmanager
    def _span(self, name: str, tags: list[str], **inputs: Any) -> Iterator[SpanHandle]:
        if not self.settings.enabled:
            yield SpanHandle()
            return
        with trace(
            name=name,
            run_type="chain",
            inputs=inputs,
            tags=tags,
            client=self.client,
            project_name=self.settings.project,
            parent=get_current_run_tree(),
        ) as run:
            yield SpanHandle(run)
