from __future__ import annotations

from collections import defaultdict

from tgraph.core.graph import TGraph


def segment_view(graph: TGraph) -> dict:
    segments: dict[str, list[dict[str, str]]] = defaultdict(list)
    for node in graph.nodes:
        for port in node.ports:
            if port.cidr:
                segments[port.cidr].append({"node": node.id, "port": port.id})
    return {
        "segments": [
            {"cidr": cidr, "ports": sorted(ports, key=lambda item: (item["node"], item["port"]))}
            for cidr, ports in sorted(segments.items())
        ]
    }

