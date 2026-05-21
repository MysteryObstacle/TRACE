from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any


class BackendResolutionError(Exception):
    pass


def add_trace_backend_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--trace-root", default=None, help="Path to the TRACE repository root.")
    parser.add_argument("--trace-python", default=None, help="Python executable with TRACE installed.")


def resolve_trace_backend(trace_root: str | None = None, trace_python: str | None = None) -> dict[str, Any]:
    selected_python = trace_python or os.environ.get("TGRAPH_TRACE_PYTHON")
    if selected_python:
        return {"mode": "python", "python": selected_python}

    selected_root = trace_root or os.environ.get("TGRAPH_TRACE_ROOT")
    root_path: Path | None = None
    if selected_root:
        root_path = Path(selected_root).resolve()
        src_path = root_path / "src"
        if not src_path.exists():
            raise BackendResolutionError(f"TRACE src directory not found: {src_path}")
        sys.path.insert(0, str(src_path))

    module = importlib.import_module("trace.tools.tgraph")
    module_file = Path(getattr(module, "__file__", "")).resolve()
    if root_path is not None and root_path not in module_file.parents:
        raise BackendResolutionError(f"loaded trace module outside TRACE root: {module_file}")
    return {"mode": "inprocess", "module": module}


def json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def print_json(payload: Any, exit_code: int = 0) -> None:
    print(json_dumps(payload))
    raise SystemExit(exit_code)

