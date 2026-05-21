from pathlib import Path
import importlib
import sys


def test_trace_cli_bootstrap_loads_project_trace_package(monkeypatch):
    monkeypatch.delitem(sys.modules, "trace", raising=False)

    trace_cli = importlib.import_module("trace_cli")
    module = trace_cli._bootstrap_trace_package()

    assert Path(module.__file__).resolve().name == "__init__.py"
    assert Path(module.__file__).resolve().parent.name == "trace"
