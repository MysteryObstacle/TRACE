from __future__ import annotations

from tgraph.core.graph import TGraph


def get_node(graph: TGraph, node_id: str) -> dict:
    for node in graph.nodes:
        if node.id == node_id:
            return {"node": node.model_dump(mode="json")}
    return {"node": None}

