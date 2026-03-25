from __future__ import annotations

import json
from pathlib import Path

from tools.tgraph.model import TGraph


def load_tgraph_json(source: str | Path) -> TGraph:
    path = Path(source)
    try:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
        else:
            payload = json.loads(str(source))
    except json.JSONDecodeError as exc:
        raise ValueError("import_parse_error:json") from exc

    return TGraph.model_validate(payload)
