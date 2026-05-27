from __future__ import annotations

from collections import defaultdict

from tgraph.core.graph import TGraph


def cidr_view(graph: TGraph) -> dict:
    return {
        "cidrs": [
            {"cidr": cidr, "ports": ports_in_cidr(graph, cidr)}
            for cidr in list_cidrs(graph)
        ]
    }


def list_cidrs(graph: TGraph) -> list[str]:
    cidrs = {port.cidr for node in graph.nodes for port in node.ports if port.cidr}
    return sorted(cidrs)


def ports_in_cidr(graph: TGraph, cidr: str) -> list[dict[str, str]]:
    ports: list[dict[str, str]] = []
    for node in graph.nodes:
        for port in node.ports:
            if port.cidr == cidr:
                ports.append({"node": node.id, "port": port.id})
    return sorted(ports, key=lambda item: (item["node"], item["port"]))


def nodes_in_cidr(graph: TGraph, cidr: str) -> list[dict]:
    nodes = []
    seen: set[str] = set()
    for node in graph.nodes:
        if node.id in seen:
            continue
        if any(port.cidr == cidr for port in node.ports):
            nodes.append(node.model_dump(mode="json"))
            seen.add(node.id)
    return nodes
