from __future__ import annotations

from typing import Any, Mapping

from tgraph import TGraph, init_physical_skeleton


def build_physical_seed_graph(
    logical_graph: TGraph | dict[str, Any],
    *,
    defaults_by_type: Mapping[str, Mapping[str, Any]] | None = None,
) -> TGraph:
    return init_physical_skeleton(logical_graph, defaults_by_type=defaults_by_type)
