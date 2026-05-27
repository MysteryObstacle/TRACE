from __future__ import annotations

from tgraph.core.graph import TGraph


def port_owner_map(graph: TGraph) -> dict[str, str]:
    return {
        port.id: node.id
        for node in graph.nodes
        for port in node.ports
    }

