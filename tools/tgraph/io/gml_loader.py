from __future__ import annotations

from pathlib import Path

from tools.tgraph.model import TGraph


def load_tgraph_gml(source: str | Path, target_profile: str = "logical.v1") -> TGraph:
    _ = source
    _ = target_profile
    raise NotImplementedError("import_not_implemented:gml")
