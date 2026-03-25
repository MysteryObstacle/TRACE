from __future__ import annotations

from dataclasses import dataclass, field

from tools.tgraph.model.link import Link
from tools.tgraph.model.node import Node
from tools.tgraph.model.port import Port


@dataclass(slots=True)
class TGraphIndexes:
    node_by_id: dict[str, Node] = field(default_factory=dict)
    port_by_id: dict[str, Port] = field(default_factory=dict)
    port_owner: dict[str, str] = field(default_factory=dict)
    link_by_id: dict[str, Link] = field(default_factory=dict)
    links_by_node: dict[str, list[Link]] = field(default_factory=dict)
    links_by_port: dict[str, list[Link]] = field(default_factory=dict)


def build_indexes(graph: "TGraph") -> TGraphIndexes:
    indexes = TGraphIndexes()

    for node in graph.nodes:
        indexes.node_by_id[node.id] = node
        indexes.links_by_node.setdefault(node.id, [])
        for port in node.ports:
            indexes.port_by_id[port.id] = port
            indexes.port_owner[port.id] = node.id
            indexes.links_by_port.setdefault(port.id, [])

    for link in graph.links:
        indexes.link_by_id[link.id] = link
        if link.from_node is not None:
            indexes.links_by_node.setdefault(link.from_node, []).append(link)
        if link.to_node is not None and link.to_node != link.from_node:
            indexes.links_by_node.setdefault(link.to_node, []).append(link)
        indexes.links_by_port.setdefault(link.from_port, []).append(link)
        indexes.links_by_port.setdefault(link.to_port, []).append(link)

    return indexes
