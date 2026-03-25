from __future__ import annotations

from typing import Any

from tools.tgraph.validate.issues import issue


REQUIRED_TOP_LEVEL_FIELDS = ("profile", "nodes", "links")


def f1_format(tgraph: dict[str, Any], **_: Any) -> list[dict[str, Any]]:
    if not isinstance(tgraph, dict):
        return [issue("invalid_top_level_type", "tgraph payload must be an object", "topology", json_paths=["$"])]

    issues: list[dict[str, Any]] = []
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in tgraph:
            issues.append(
                issue(
                    "missing_top_level_field",
                    f"missing top-level field '{field}'",
                    "topology",
                    json_paths=[f"$.{field}"],
                )
            )

    if issues:
        return issues

    if not isinstance(tgraph["profile"], str):
        issues.append(issue("invalid_top_level_field_type", "profile must be a string", "topology", json_paths=["$.profile"]))
    if not isinstance(tgraph["nodes"], list):
        issues.append(issue("invalid_top_level_field_type", "nodes must be a list", "topology", json_paths=["$.nodes"]))
    if not isinstance(tgraph["links"], list):
        issues.append(issue("invalid_top_level_field_type", "links must be a list", "topology", json_paths=["$.links"]))
    return issues
