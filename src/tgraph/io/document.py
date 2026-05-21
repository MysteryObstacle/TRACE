from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from tgraph.core.errors import DocumentError
from tgraph.core.graph import TGraph

ALLOWED_TOP_LEVEL_FIELDS = {"stage", "nodes", "links"}


def parse_tgraph_document(raw: Any) -> TGraph:
    if not isinstance(raw, dict):
        raise DocumentError("TGraph document must be a JSON object")

    unknown = sorted(set(raw) - ALLOWED_TOP_LEVEL_FIELDS)
    if unknown:
        raise DocumentError(
            "TGraph document contains unsupported top-level fields",
            details={"fields": unknown},
        )

    try:
        return TGraph.model_validate(raw)
    except ValidationError as exc:
        raise DocumentError("TGraph document failed schema validation", details={"errors": exc.errors()}) from exc


def dump_tgraph_document(graph: TGraph) -> dict[str, Any]:
    return graph.model_dump(mode="json")

