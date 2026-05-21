from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ValidationIssue(BaseModel):
    code: str
    message: str
    severity: Literal["error", "warning"] = "error"
    location: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationReport(BaseModel):
    ok: bool
    issues: list[ValidationIssue] = Field(default_factory=list)

    @classmethod
    def from_issues(cls, issues: list[ValidationIssue]) -> "ValidationReport":
        return cls(ok=not any(issue.severity == "error" for issue in issues), issues=issues)

