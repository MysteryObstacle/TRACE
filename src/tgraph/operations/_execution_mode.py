from __future__ import annotations

import os


def use_inline_execution() -> bool:
    """Run sandboxed checkpoint/mutation workers in-process (used by tests on Windows)."""

    return os.environ.get("TGRAPH_EXECUTION_MODE", "").strip().lower() == "inline"
