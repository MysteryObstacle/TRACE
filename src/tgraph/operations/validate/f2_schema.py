from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from tgraph.core.graph import TGraph
from tgraph.operations.validate.issues import ValidationIssue


def f2_schema(raw: Any) -> list[ValidationIssue]:
    try:
        TGraph.model_validate(raw)
    except ValidationError as exc:
        return [
            ValidationIssue(
                code="schema_validation_error",
                message="TGraph document failed schema validation",
                details={"errors": exc.errors()},
            )
        ]
    return []

