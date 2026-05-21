from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from trace_backend import BackendResolutionError, add_trace_backend_args, print_json, resolve_trace_backend


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply a declarative TGraph artifact patch.")
    add_trace_backend_args(parser)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--patch", required=True)
    parser.add_argument("--stage", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--include-artifact", action="store_true")
    args = parser.parse_args()

    try:
        resolve_trace_backend(args.trace_root, args.trace_python)
        from trace.tools.tgraph.patch import apply_artifact_patch

        artifact = _read_json(Path(args.artifact))
        patch = _read_json(Path(args.patch))
        needs_artifact = bool(args.out)
        result = apply_artifact_patch(
            artifact,
            patch,
            stage=args.stage,
            dry_run=True if args.dry_run else None,
            include_artifact=args.include_artifact or needs_artifact,
        )
        artifact_result = result.get("artifact")
        if result.get("committed") and args.out and artifact_result is not None:
            _write_json(Path(args.out), artifact_result)
        if not args.include_artifact:
            result["artifact"] = None
        print_json(result, 0 if result.get("ok") else 1)
    except BackendResolutionError as exc:
        print_json(_error("backend_resolution_error", str(exc)), 1)
    except Exception as exc:
        print_json(_error("patch_schema_error", str(exc)), 1)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "committed": False, "error": {"code": code, "message": message}}


if __name__ == "__main__":
    main()

