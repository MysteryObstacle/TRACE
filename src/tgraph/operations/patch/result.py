from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from tgraph.core.graph import TGraph
from tgraph.operations.validate import ValidationReport
from tgraph.operations.patch.diff import empty_diff


class PatchResult(BaseModel):
    ok: bool
    would_commit: bool = False
    accepted_ops: list[dict[str, Any]] = Field(default_factory=list)
    rejected_ops: list[dict[str, Any]] = Field(default_factory=list)
    diff: dict[str, Any] = Field(default_factory=empty_diff)
    validation: ValidationReport | None = None
    graph: TGraph | None = None
    error: dict[str, Any] | None = None


class PatchParseResult(BaseModel):
    ok: bool
    patch: "TGraphPatch | None" = None
    error: dict[str, Any] | None = None


from tgraph.operations.patch.schema import TGraphPatch  # noqa: E402

PatchParseResult.model_rebuild()

