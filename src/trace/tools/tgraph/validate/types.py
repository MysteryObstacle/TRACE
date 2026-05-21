from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class IssueProvenance(BaseModel):
    layer: Literal["f1", "f2", "f3", "f4"]
    source: Literal["builtin", "authored_check"]
    check_id: str | None = None
    constraint_ids: list[str] = Field(default_factory=list)
    func: str | None = None
    impl_source: Literal["sdk", "custom", "unknown"] | None = None
    args: dict[str, Any] | None = None
    artifact: str | None = None


class ValidationIssue(BaseModel):
    code: str
    message: str
    severity: str
    targets: list[str] = Field(default_factory=list)
    json_paths: list[str] = Field(default_factory=list)
    provenance: IssueProvenance | None = None


class ValidationReport(BaseModel):
    ok: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
