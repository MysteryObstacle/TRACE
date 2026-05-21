from __future__ import annotations

from typing import Any

from trace.tools.tgraph.validate.issues import issue


def f1_format(tgraph: dict[str, Any], **_: Any) -> list[dict[str, Any]]:
    if not isinstance(tgraph, dict):
        return [
            issue(
                "invalid_top_level_type",
                "tgraph payload must be an object",
                json_paths=["$"],
                provenance={"layer": "f1", "source": "builtin"},
            )
        ]

    issues: list[dict[str, Any]] = []
    for field in ("profile", "nodes", "links"):
        if field not in tgraph:
            issues.append(
                issue(
                    "missing_top_level_field",
                    f"missing top-level field '{field}'",
                    json_paths=[f"$.{field}"],
                    provenance={"layer": "f1", "source": "builtin"},
                )
            )
    if issues:
        return issues
    if not isinstance(tgraph["profile"], str):
        issues.append(
            issue(
                "invalid_top_level_field_type",
                "profile must be a string",
                json_paths=["$.profile"],
                provenance={"layer": "f1", "source": "builtin"},
            )
        )
    if not isinstance(tgraph["nodes"], list):
        issues.append(
            issue(
                "invalid_top_level_field_type",
                "nodes must be a list",
                json_paths=["$.nodes"],
                provenance={"layer": "f1", "source": "builtin"},
            )
        )
    if not isinstance(tgraph["links"], list):
        issues.append(
            issue(
                "invalid_top_level_field_type",
                "links must be a list",
                json_paths=["$.links"],
                provenance={"layer": "f1", "source": "builtin"},
            )
        )
    return issues
