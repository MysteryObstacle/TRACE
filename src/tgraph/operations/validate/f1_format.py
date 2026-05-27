from __future__ import annotations

from typing import Any

from tgraph.io.document import ALLOWED_TOP_LEVEL_FIELDS
from tgraph.operations.validate.issues import ValidationIssue, validation_issue


def f1_format(raw: Any) -> list[ValidationIssue]:
    if not isinstance(raw, dict):
        return [validation_issue("document_not_object", "TGraph document must be a JSON object")]

    unknown = sorted(set(raw) - ALLOWED_TOP_LEVEL_FIELDS)
    if unknown:
        return [
            validation_issue(
                "unknown_top_level_field",
                "TGraph document contains unsupported top-level fields",
                details={"fields": unknown},
            )
        ]

    return []
