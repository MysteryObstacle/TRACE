from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from trace_backend import BackendResolutionError, add_trace_backend_args, print_json, resolve_trace_backend


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a TGraph artifact envelope.")
    add_trace_backend_args(parser)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--stage", default=None)
    parser.add_argument("--query", required=True, choices=["topology", "node", "links", "checkpoints"])
    parser.add_argument("--id", default=None)
    parser.add_argument("--node", default=None)
    parser.add_argument("--text", default=None)
    args = parser.parse_args()

    try:
        resolve_trace_backend(args.trace_root, args.trace_python)
        from trace.tools.tgraph.patch import STAGE_FIELDS, infer_artifact_stage
        from trace.tools.tgraph.runtime import TGraphRuntime

        artifact = _read_json(Path(args.artifact))
        stage = args.stage or infer_artifact_stage(artifact)
        graph_field, checkpoints_field, _ = STAGE_FIELDS[stage]
        runtime = TGraphRuntime.from_json(artifact[graph_field])

        if args.query == "topology":
            print_json(runtime.topology_view())
        elif args.query == "node":
            if not args.id:
                raise ValueError("--id is required for node query")
            print_json(runtime.get_node(args.id))
        elif args.query == "links":
            print_json(runtime.get_links(node_id=args.node))
        elif args.query == "checkpoints":
            print_json(_find_checkpoints(artifact.get(checkpoints_field, []), args.text or ""))
    except BackendResolutionError as exc:
        print_json({"ok": False, "error": {"code": "backend_resolution_error", "message": str(exc)}}, 1)
    except Exception as exc:
        print_json({"ok": False, "error": {"code": "artifact_shape_error", "message": str(exc)}}, 1)


def _find_checkpoints(checkpoints: list[dict[str, Any]], text: str) -> list[dict[str, Any]]:
    needle = text.lower().strip()
    if not needle:
        return checkpoints
    result = []
    for checkpoint in checkpoints:
        haystack = json.dumps(checkpoint, ensure_ascii=False).lower()
        if needle in haystack:
            result.append(checkpoint)
    return result


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()

