from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tgraph.core.errors import DocumentError
from tgraph.core.graph import TGraph
from tgraph.core.normalize import normalize_graph
from tgraph.io.document import dump_tgraph_document, parse_tgraph_document


def load_tgraph(value: dict[str, Any] | str | Path, *, normalize: bool = True) -> TGraph:
    raw = _load_raw(value)
    graph = parse_tgraph_document(raw)
    if normalize:
        return normalize_graph(graph)
    return graph


def dump_tgraph(graph: TGraph | dict[str, Any], *, as_json: bool = False) -> dict[str, Any] | str:
    current = graph if isinstance(graph, TGraph) else parse_tgraph_document(graph)
    payload = dump_tgraph_document(current)
    if as_json:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return payload


def _load_raw(value: dict[str, Any] | str | Path) -> Any:
    if isinstance(value, dict):
        return value
    if isinstance(value, Path):
        return _load_json_text(value.read_text(encoding="utf-8"))
    if isinstance(value, str):
        candidate = Path(value)
        if candidate.exists():
            return _load_json_text(candidate.read_text(encoding="utf-8"))
        return _load_json_text(value)
    raise DocumentError("unsupported TGraph input type", details={"type": type(value).__name__})


def _load_json_text(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise DocumentError("invalid TGraph JSON", details={"error": str(exc)}) from exc

