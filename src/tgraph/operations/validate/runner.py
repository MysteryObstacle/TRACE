from __future__ import annotations

from typing import Any

from tgraph.core.graph import TGraph
from tgraph.io.document import parse_tgraph_document
from tgraph.operations.validate.f1_format import f1_format
from tgraph.operations.validate.f2_schema import f2_schema
from tgraph.operations.validate.f3_graph import f3_graph
from tgraph.operations.validate.f4_intent import f4_intent
from tgraph.operations.validate.issues import ValidationIssue, ValidationReport
from tgraph.operations.validate.policy import ValidationContext, ValidationPolicy


def validate_document(raw: Any, policy: ValidationPolicy | None = None, context: ValidationContext | None = None) -> ValidationReport:
    effective_policy = policy or ValidationPolicy()
    issues: list[ValidationIssue] = []
    graph: TGraph | None = None

    if "f1" in effective_policy.levels:
        issues.extend(f1_format(raw))

    if "f2" in effective_policy.levels and not _has_error(issues):
        issues.extend(f2_schema(raw))

    if any(level in effective_policy.levels for level in ("f3", "f4")) and not _has_error(issues):
        try:
            graph = parse_tgraph_document(raw)
        except Exception:
            graph = None
    if graph is not None and "f3" in effective_policy.levels:
        issues.extend(f3_graph(graph))
    if graph is not None and "f4" in effective_policy.levels:
        issues.extend(f4_intent(graph, context))

    return ValidationReport.from_issues(issues)


def validate_graph(
    graph: TGraph | dict[str, Any],
    policy: ValidationPolicy | None = None,
    context: ValidationContext | None = None,
) -> ValidationReport:
    current = graph if isinstance(graph, TGraph) else TGraph.model_validate(graph)
    effective_policy = policy or ValidationPolicy()
    issues: list[ValidationIssue] = []

    if "f1" in effective_policy.levels:
        issues.extend(f1_format(current.model_dump(mode="json")))
    if "f2" in effective_policy.levels:
        issues.extend(f2_schema(current.model_dump(mode="json")))
    if "f3" in effective_policy.levels:
        issues.extend(f3_graph(current))
    if "f4" in effective_policy.levels:
        issues.extend(f4_intent(current, context))

    return ValidationReport.from_issues(issues)


def _has_error(issues: list[ValidationIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)
