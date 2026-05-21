from __future__ import annotations

from collections import Counter

from tgraph.core.graph import TGraph


def graph_summary(graph: TGraph) -> dict:
    return {
        "stage": graph.stage,
        "node_count": len(graph.nodes),
        "link_count": len(graph.links),
        "node_types": dict(sorted(Counter(node.type for node in graph.nodes).items())),
    }

