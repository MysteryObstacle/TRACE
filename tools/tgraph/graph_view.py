from __future__ import annotations

import networkx as nx

from tools.tgraph.model import TGraph, ensure_tgraph


def to_networkx(graph: TGraph | dict) -> nx.MultiGraph:
    model = ensure_tgraph(graph)
    view = nx.MultiGraph()

    for node in model.nodes:
        view.add_node(node.id, type=node.type, label=node.label)

    indexes = model.build_indexes()
    for link in model.links:
        from_node = link.from_node or indexes.port_owner.get(link.from_port)
        to_node = link.to_node or indexes.port_owner.get(link.to_port)
        if from_node is None or to_node is None:
            continue
        view.add_edge(
            from_node,
            to_node,
            key=link.id,
            link_id=link.id,
            from_port=link.from_port,
            to_port=link.to_port,
            from_node=from_node,
            to_node=to_node,
        )

    return view
