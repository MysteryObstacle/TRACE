from __future__ import annotations

from typing import Any

from tools.tgraph.validate.f1_format import f1_format
from tools.tgraph.validate.f2_schema import f2_schema
from tools.tgraph.validate.f3_consistency import f3_consistency


def validate_tgraph_payload(tgraph: dict[str, Any]) -> list[dict[str, Any]]:
    issues = list(f1_format(tgraph))
    if issues:
        return issues

    issues = list(f2_schema(tgraph))
    if issues:
        return issues

    issues.extend(f3_consistency(tgraph))
    return issues
