from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator


@dataclass
class TraceRecorder:
    enabled: bool = False

    @contextmanager
    def root_run(self, **_: object) -> Iterator[None]:
        yield

    @contextmanager
    def stage_run(self, **_: object) -> Iterator[None]:
        yield

    @contextmanager
    def validation_run(self, **_: object) -> Iterator[None]:
        yield

    @contextmanager
    def patch_run(self, **_: object) -> Iterator[None]:
        yield
