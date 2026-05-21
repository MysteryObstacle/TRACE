from __future__ import annotations

import json
from typing import Any

from tgraph import dump_tgraph, normalize_graph

from trace.tools.tgraph.model import to_standalone_graph
from trace.tools.tgraph.patch import STAGE_FIELDS, infer_artifact_stage


def export_artifact(artifact: dict[str, Any], *, target: str, stage: str | None = None) -> dict[str, Any]:
    try:
        selected_stage = stage or infer_artifact_stage(artifact)
        graph_field, _, _ = STAGE_FIELDS[str(selected_stage)]
        graph = normalize_graph(to_standalone_graph(artifact[graph_field], stage=str(selected_stage)))
    except Exception as exc:
        return {"ok": False, "files": [], "error": {"code": "export_error", "message": str(exc)}}

    if target != "tgraph-json":
        return {
            "ok": False,
            "files": [],
            "error": {"code": "export_error", "message": f"unsupported export target: {target}"},
        }

    return {
        "ok": True,
        "files": [{"path": "tgraph.json", "content": json.dumps(dump_tgraph(graph), indent=2, ensure_ascii=False)}],
        "error": None,
    }

