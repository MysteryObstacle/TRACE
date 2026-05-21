from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from trace_backend import BackendResolutionError, add_trace_backend_args, print_json, resolve_trace_backend


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a TGraph artifact envelope.")
    add_trace_backend_args(parser)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--stage", default=None)
    parser.add_argument("--target", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    try:
        resolve_trace_backend(args.trace_root, args.trace_python)
        from trace.tools.tgraph.export import export_artifact

        artifact = _read_json(Path(args.artifact))
        result = export_artifact(artifact, target=args.target, stage=args.stage)
        if result.get("ok") and args.out:
            out_dir = Path(args.out)
            written = []
            for file_item in result.get("files", []):
                path = out_dir / file_item["path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(file_item.get("content", ""), encoding="utf-8")
                written.append({"path": str(path)})
            result["files"] = written
        print_json(result, 0 if result.get("ok") else 1)
    except BackendResolutionError as exc:
        print_json(_error("backend_resolution_error", str(exc)), 1)
    except Exception as exc:
        print_json(_error("export_error", str(exc)), 1)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "files": [], "error": {"code": code, "message": message}}


if __name__ == "__main__":
    main()

