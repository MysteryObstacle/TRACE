from __future__ import annotations

from typing import Any

from tgraph import TGraph, init_logical_skeleton


def build_logical_seed_graph(ground_artifact: dict[str, Any]) -> TGraph:
    return init_logical_skeleton(ground_artifact.get("node_groups", []))
