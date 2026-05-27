from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GeneratedFile(BaseModel):
    path: str
    content: str


class EmitResult(BaseModel):
    ok: bool
    target: str
    files: list[GeneratedFile] = Field(default_factory=list)
    error: dict[str, Any] | None = None

