from pathlib import Path
import importlib
import os
import subprocess
import sys


def test_trace_cli_bootstrap_loads_project_trace_package(monkeypatch):
    monkeypatch.delitem(sys.modules, "trace", raising=False)

    trace_cli = importlib.import_module("trace_cli")
    module = trace_cli._bootstrap_trace_package()

    assert Path(module.__file__).resolve().name == "__init__.py"
    assert Path(module.__file__).resolve().parent.name == "trace"


def test_trace_cli_module_invocation_shows_help():
    repo_root = Path(__file__).resolve().parents[3]
    env = {
        **os.environ,
        "PYTHONPATH": str(repo_root / "src"),
    }
    result = subprocess.run(
        [sys.executable, "-m", "trace_cli", "--help"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "TRACE CLI" in result.stdout
