from __future__ import annotations

from typing import Any

from tgraph.core.graph import TGraph


def normalize_graph(graph: TGraph | dict[str, Any]) -> TGraph:
    current = graph if isinstance(graph, TGraph) else TGraph.model_validate(graph)
    data = current.model_dump(mode="json")

    nodes = sorted(data.get("nodes", []), key=lambda item: item["id"])
    for node in nodes:
        node["ports"] = sorted(node.get("ports", []), key=lambda item: item["id"])
    data["nodes"] = nodes

    normalized_links: list[dict[str, Any]] = []
    for link in data.get("links", []):
        from_node = str(link["from_node"])
        to_node = str(link["to_node"])
        if from_node <= to_node:
            node_a = from_node
            port_a = str(link["from_port"])
            node_b = to_node
            port_b = str(link["to_port"])
        else:
            node_a = to_node
            port_a = str(link["to_port"])
            node_b = from_node
            port_b = str(link["from_port"])
        key = _link_key(str(link["id"]), node_a, node_b)
        normalized_links.append(
            {
                "id": _link_id(node_a, node_b, key),
                "from_port": port_a,
                "to_port": port_b,
                "from_node": node_a,
                "to_node": node_b,
            }
        )
    data["links"] = sorted(normalized_links, key=lambda item: item["id"])

    return TGraph.model_validate(data)


def _link_id(from_node: str, to_node: str, key: str) -> str:
    return f"{from_node}-{to_node}-{key}"


def _link_key(link_id: str, from_node: str, to_node: str) -> str:
    prefix = f"{from_node}-{to_node}-"
    if link_id.startswith(prefix):
        key = link_id.removeprefix(prefix)
        if key and "-" not in key:
            return key
    return "1"
