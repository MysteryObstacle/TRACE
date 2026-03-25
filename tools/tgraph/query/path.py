from __future__ import annotations

import networkx as nx

from tools.tgraph.graph_view import to_networkx
from tools.tgraph.model import TGraph, ensure_tgraph


def shortest_path(graph: TGraph | dict, src_node: str, dst_node: str) -> list[str]:
    if src_node == dst_node:
        return [src_node]

    model = ensure_tgraph(graph)
    indexes = model.build_indexes()
    if src_node not in indexes.node_by_id:
        raise KeyError(f"query_node_not_found:{src_node}")
    if dst_node not in indexes.node_by_id:
        raise KeyError(f"query_node_not_found:{dst_node}")

    view = to_networkx(model)
    try:
        return list(nx.shortest_path(view, src_node, dst_node))
    except nx.NetworkXNoPath:
        return []
