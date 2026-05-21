from __future__ import annotations

from typing import Any

from tgraph.io.document import ALLOWED_TOP_LEVEL_FIELDS
from tgraph.operations.validate.issues import ValidationIssue


def f1_format(raw: Any) -> list[ValidationIssue]:
    if not isinstance(raw, dict):
        return [ValidationIssue(code="document_not_object", message="TGraph document must be a JSON object")]

    unknown = sorted(set(raw) - ALLOWED_TOP_LEVEL_FIELDS)
    if unknown:
        return [
            ValidationIssue(
                code="unknown_top_level_field",
                message="TGraph document contains unsupported top-level fields",
                details={"fields": unknown},
            )
        ]

    return []

