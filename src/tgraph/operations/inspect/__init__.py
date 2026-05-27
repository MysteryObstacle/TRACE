from __future__ import annotations

from typing import Any

from tgraph.core.graph import TGraph
from tgraph.operations.inspect.cidrs import cidr_view, list_cidrs, nodes_in_cidr, ports_in_cidr
from tgraph.operations.inspect.diff import diff as _diff_view
from tgraph.operations.inspect.links import get_links
from tgraph.operations.inspect.nodes import get_node
from tgraph.operations.inspect.paths import find_path
from tgraph.operations.inspect.summary import graph_summary


def inspect_graph(graph: TGraph | dict[str, Any], *, view: str = "summary", **kwargs: Any) -> dict:
    current = graph if isinstance(graph, TGraph) else TGraph.model_validate(graph)
    if view == "summary":
        return graph_summary(current)
    if view == "node":
        node_id = kwargs.get("node_id")
        if not node_id:
            raise ValueError("inspect_graph view='node' requires node_id")
        return get_node(current, str(node_id))
    if view == "links":
        return get_links(
            current,
            node_id=kwargs.get("node_id"),
            port_id=kwargs.get("port_id"),
        )
    if view == "path":
        source = kwargs.get("source")
        target = kwargs.get("target")
        if not source or not target:
            raise ValueError("inspect_graph view='path' requires source and target")
        return find_path(current, source=str(source), target=str(target))
    if view == "cidrs":
        return cidr_view(current)
    if view == "diff":
        baseline = kwargs.get("baseline")
        if baseline is None:
            raise ValueError("inspect_graph(view='diff') requires a baseline TGraph")
        baseline_graph = baseline if isinstance(baseline, TGraph) else TGraph.model_validate(baseline)
        return _diff_view(current, baseline_graph)
    raise ValueError(f"unknown inspect view: {view}")


__all__ = ["inspect_graph", "list_cidrs", "nodes_in_cidr", "ports_in_cidr"]
