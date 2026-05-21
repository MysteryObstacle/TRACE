from __future__ import annotations

from tgraph.core.graph import Link, TGraph
from tgraph.operations.inspect.ports import port_owner_map


def get_links(graph: TGraph, *, node_id: str | None = None, port_id: str | None = None) -> dict:
    owners = port_owner_map(graph)
    links: list[Link] = []
    for link in graph.links:
        if port_id and port_id not in {link.from_port, link.to_port}:
            continue
        if node_id:
            link_nodes = {link.from_node or owners.get(link.from_port), link.to_node or owners.get(link.to_port)}
            if node_id not in link_nodes:
                continue
        links.append(link)
    return {"links": [link.model_dump(mode="json") for link in links]}

