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

    port_owner: dict[str, str] = {}
    for node in nodes:
        for port in node.get("ports", []):
            port_owner[str(port["id"])] = str(node["id"])

    normalized_links: list[dict[str, Any]] = []
    for link in data.get("links", []):
        port_a = str(link["from_port"])
        port_b = str(link["to_port"])
        from_port, to_port = sorted((port_a, port_b))
        normalized_links.append(
            {
                "id": _link_id(from_port, to_port),
                "from_port": from_port,
                "to_port": to_port,
                "from_node": port_owner.get(from_port),
                "to_node": port_owner.get(to_port),
            }
        )
    data["links"] = sorted(normalized_links, key=lambda item: item["id"])

    return TGraph.model_validate(data)


def _link_id(from_port: str, to_port: str) -> str:
    return f"{from_port}--{to_port}"

