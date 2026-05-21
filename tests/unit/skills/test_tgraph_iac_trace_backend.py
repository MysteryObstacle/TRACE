from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "skills" / "tgraph-iac"
TRACE_ROOT = Path(__file__).resolve().parents[3]


def _load_trace_backend():
    path = SKILL_ROOT / "scripts" / "trace_backend.py"
    spec = importlib.util.spec_from_file_location("tgraph_iac_trace_backend", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_resolve_trace_root_inserts_src_and_imports_project_trace(monkeypatch):
    module = _load_trace_backend()
    monkeypatch.delenv("TGRAPH_TRACE_ROOT", raising=False)
    monkeypatch.delenv("TGRAPH_TRACE_PYTHON", raising=False)

    resolved = module.resolve_trace_backend(trace_root=str(TRACE_ROOT))

    assert resolved["mode"] == "inprocess"
    loaded_file = Path(resolved["module"].__file__).resolve()
    assert TRACE_ROOT in loaded_file.parents
    assert loaded_file.name == "__init__.py"


def test_resolve_backend_reports_missing_trace_root(tmp_path):
    module = _load_trace_backend()

    try:
        module.resolve_trace_backend(trace_root=str(tmp_path))
    except module.BackendResolutionError as exc:
        assert "TRACE src directory not found" in str(exc)
    else:
        raise AssertionError("expected BackendResolutionError")


def test_add_trace_backend_args_accepts_trace_root_argument():
    module = _load_trace_backend()
    parser = argparse.ArgumentParser()
    module.add_trace_backend_args(parser)

    args = parser.parse_args(["--trace-root", str(TRACE_ROOT), "--trace-python", "python"])

    assert args.trace_root == str(TRACE_ROOT)
    assert args.trace_python == "python"
