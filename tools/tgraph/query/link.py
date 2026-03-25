from __future__ import annotations

from tools.tgraph.model import Link, TGraph, ensure_tgraph


def get_link(graph: TGraph | dict, link_id: str) -> Link:
    model = ensure_tgraph(graph)
    indexes = model.build_indexes()
    if link_id not in indexes.link_by_id:
        raise KeyError(f"query_link_not_found:{link_id}")
    return indexes.link_by_id[link_id]


def list_links(graph: TGraph | dict, node_id: str | None = None, port_id: str | None = None) -> list[Link]:
    model = ensure_tgraph(graph)
    indexes = model.build_indexes()

    if node_id is None and port_id is None:
        return list(model.links)

    if node_id is not None and node_id not in indexes.node_by_id:
        raise KeyError(f"query_node_not_found:{node_id}")
    if port_id is not None and port_id not in indexes.port_by_id:
        raise KeyError(f"query_port_not_found:{port_id}")

    if node_id is not None and port_id is not None:
        node_links = {link.id: link for link in indexes.links_by_node.get(node_id, [])}
        return [link for link in indexes.links_by_port.get(port_id, []) if link.id in node_links]
    if node_id is not None:
        return list(indexes.links_by_node.get(node_id, []))
    return list(indexes.links_by_port.get(port_id or "", []))
