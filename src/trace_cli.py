from __future__ import annotations

from importlib import import_module, util
from pathlib import Path
import sys
from types import ModuleType


def _bootstrap_trace_package() -> ModuleType:
    existing = sys.modules.get("trace")
    if existing is not None and getattr(existing, "__file__", "").endswith("__init__.py"):
        return existing

    package_dir = Path(__file__).resolve().with_name("trace")
    spec = util.spec_from_file_location(
        "trace",
        package_dir / "__init__.py",
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(f"Unable to load TRACE package from {package_dir}")

    module = util.module_from_spec(spec)
    sys.modules["trace"] = module
    spec.loader.exec_module(module)
    return module


_bootstrap_trace_package()
app = import_module("trace.main").app
