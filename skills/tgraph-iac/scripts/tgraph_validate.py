from __future__ import annotations

import argparse
import json
from pathlib import Path

from trace_backend import BackendResolutionError, add_trace_backend_args, print_json, resolve_trace_backend, validate_stage_artifact


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a TGraph artifact envelope.")
    add_trace_backend_args(parser)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--stage", default=None)
    parser.add_argument("--logical-artifact", default=None)
    parser.add_argument("--levels", default="f1,f2,f3,f4")
    args = parser.parse_args()

    try:
        resolve_trace_backend(args.trace_root, args.trace_python)

        artifact = _read_json(Path(args.artifact))
        logical_artifact = _read_json(Path(args.logical_artifact)) if args.logical_artifact else None
        report = validate_stage_artifact(
            artifact,
            stage=args.stage,
            levels=_levels(args.levels),
            logical_artifact=logical_artifact,
        )
        print_json(report, 0 if report.get("ok") else 1)
    except BackendResolutionError as exc:
        print_json(_error("backend_resolution_error", str(exc)), 1)
    except Exception as exc:
        print_json(_error("artifact_shape_error", str(exc)), 1)


def _levels(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "issues": [], "error": {"code": code, "message": message}}


if __name__ == "__main__":
    main()

