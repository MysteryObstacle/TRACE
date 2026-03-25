from __future__ import annotations

from tools.tgraph.model import ensure_tgraph


def l2_segments(graph: dict) -> list[set[str]]:
    model = ensure_tgraph(graph)
    segments: dict[str, set[str]] = {}
    for node in model.nodes:
        for port in node.ports:
            if port.cidr:
                segments.setdefault(port.cidr, set()).add(node.id)
    return list(segments.values())
