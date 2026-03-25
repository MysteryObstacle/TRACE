from __future__ import annotations

import networkx as nx

from tools.tgraph.graph_view import to_networkx
from tools.tgraph.model import Link, Node, TGraph, ensure_tgraph


def get_node(graph: TGraph | dict, node_id: str) -> Node:
    model = ensure_tgraph(graph)
    indexes = model.build_indexes()
    if node_id not in indexes.node_by_id:
        raise KeyError(f"query_node_not_found:{node_id}")
    return indexes.node_by_id[node_id]


def list_nodes(graph: TGraph | dict, type: str | None = None) -> list[Node]:
    model = ensure_tgraph(graph)
    if type is None:
        return list(model.nodes)
    return [node for node in model.nodes if node.type == type]


def ports_of(graph: TGraph | dict, node_id: str) -> list[str]:
    return [port.id for port in get_node(graph, node_id).ports]


def neighbors(graph: TGraph | dict, node_id: str) -> set[str]:
    model = ensure_tgraph(graph)
    indexes = model.build_indexes()
    if node_id not in indexes.node_by_id:
        raise KeyError(f"query_node_not_found:{node_id}")

    view = to_networkx(model)
    try:
        return set(view.neighbors(node_id))
    except nx.NetworkXError as exc:
        raise KeyError(f"query_node_not_found:{node_id}") from exc


def degree(graph: TGraph | dict, node_id: str) -> int:
    return len(neighbors(graph, node_id))


def links_of(graph: TGraph | dict, node_id_or_port_id: str) -> list[Link]:
    model = ensure_tgraph(graph)
    indexes = model.build_indexes()
    if node_id_or_port_id in indexes.links_by_port:
        return indexes.links_by_port[node_id_or_port_id]
    if node_id_or_port_id in indexes.links_by_node:
        return indexes.links_by_node[node_id_or_port_id]
    return []
