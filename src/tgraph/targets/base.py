from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from tgraph.core.graph import TGraph
from tgraph.targets.result import EmitResult


class EmitOptions(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class TargetEmitter(Protocol):
    name: str

    def emit(self, graph: TGraph, options: EmitOptions | None = None) -> EmitResult:
        ...


class PlaceholderEmitter:
    def __init__(self, name: str) -> None:
        self.name = name

    def emit(self, graph: TGraph, options: EmitOptions | None = None) -> EmitResult:
        del graph, options
        return EmitResult(
            ok=False,
            target=self.name,
            error={
                "code": "target_not_implemented",
                "message": f"target emitter is not implemented: {self.name}",
            },
        )

