from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from trace_backend import BackendResolutionError, add_trace_backend_args, print_json, resolve_trace_backend


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a TGraph artifact envelope.")
    add_trace_backend_args(parser)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--stage", default=None)
    parser.add_argument("--levels", default="f1,f2,f3,f4")
    args = parser.parse_args()

    try:
        resolve_trace_backend(args.trace_root, args.trace_python)
        from trace.tools.tgraph.patch import STAGE_FIELDS, _run_validators, infer_artifact_stage

        artifact = _read_json(Path(args.artifact))
        stage = args.stage or infer_artifact_stage(artifact)
        graph_field, checkpoints_field, validator_field = STAGE_FIELDS[stage]
        kwargs: dict[str, Any] = {checkpoints_field: artifact.get(checkpoints_field, [])}
        constraints_field = "logical_constraints" if stage == "logical" else "physical_constraints"
        if constraints_field in artifact:
            kwargs[constraints_field] = artifact.get(constraints_field) or []
        if artifact.get(validator_field) is not None:
            kwargs[validator_field] = artifact.get(validator_field)
        report = _run_validators(artifact[graph_field], _levels(args.levels), **kwargs).model_dump(mode="json")
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

