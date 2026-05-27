from __future__ import annotations

import argparse
import json
from pathlib import Path

from trace_backend import BackendResolutionError, add_trace_backend_args, inspect_stage_artifact, print_json, resolve_trace_backend


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a TGraph artifact envelope.")
    add_trace_backend_args(parser)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--stage", default=None)
    parser.add_argument("--query", required=True, choices=["summary", "topology", "node", "links", "path", "cidrs", "support-files"])
    parser.add_argument("--id", default=None)
    parser.add_argument("--node", default=None)
    parser.add_argument("--source", default=None)
    parser.add_argument("--target", default=None)
    parser.add_argument("--text", default=None)
    args = parser.parse_args()

    try:
        resolve_trace_backend(args.trace_root, args.trace_python)

        artifact = _read_json(Path(args.artifact))
        result = inspect_stage_artifact(
            artifact,
            stage=args.stage,
            query=args.query,
            query_id=args.id,
            node=args.node,
            source=args.source,
            target=args.target,
            text=args.text,
        )
        print_json(result)
    except BackendResolutionError as exc:
        print_json({"ok": False, "error": {"code": "backend_resolution_error", "message": str(exc)}}, 1)
    except Exception as exc:
        print_json({"ok": False, "error": {"code": "artifact_shape_error", "message": str(exc)}}, 1)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()

