from __future__ import annotations

from trace.tools.tgraph.validate.f1_format import f1_format
from trace.tools.tgraph.validate.f2_schema import f2_schema
from trace.tools.tgraph.validate.f3_consistency import f3_consistency
from trace.tools.tgraph.validate.f4_intent import f4_intent
from trace.tools.tgraph.validate.types import ValidationIssue, ValidationReport


def run_default_validators(tgraph: dict, **kwargs) -> ValidationReport:
    raw_issues = [
        *f1_format(tgraph, **kwargs),
        *f2_schema(tgraph, **kwargs),
        *f3_consistency(tgraph, **kwargs),
        *f4_intent(tgraph, **kwargs),
    ]
    issues = [ValidationIssue.model_validate(item) for item in raw_issues]
    return ValidationReport(ok=not any(item.severity == "error" for item in issues), issues=issues)


__all__ = ["ValidationIssue", "ValidationReport", "run_default_validators"]

