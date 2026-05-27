from __future__ import annotations

import os

# Windows/pytest cannot reliably spawn sandbox worker processes during collection;
# run checkpoint and mutation execution in-process for the entire test session.
os.environ.setdefault("TGRAPH_EXECUTION_MODE", "inline")
