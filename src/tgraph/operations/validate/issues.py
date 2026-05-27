from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ValidationIssue(BaseModel):
    message: str
    severity: Literal["error", "warning"] = "error"
    location: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _requires_issue_kind(self) -> "ValidationIssue":
        if not self.details.get("issue_kind"):
            raise ValueError("ValidationIssue.details.issue_kind is required")
        return self


class ValidationReport(BaseModel):
    ok: bool
    issues: list[ValidationIssue] = Field(default_factory=list)

    @classmethod
    def from_issues(cls, issues: list[ValidationIssue]) -> "ValidationReport":
        return cls(ok=not any(issue.severity == "error" for issue in issues), issues=issues)


def validation_issue(
    issue_kind: str,
    message: str,
    *,
    severity: Literal["error", "warning"] = "error",
    location: str | None = None,
    details: dict[str, Any] | None = None,
) -> ValidationIssue:
    issue_details = dict(details or {})
    issue_details.setdefault("issue_kind", issue_kind)
    return ValidationIssue(
        message=message,
        severity=severity,
        location=location,
        details=issue_details,
    )
