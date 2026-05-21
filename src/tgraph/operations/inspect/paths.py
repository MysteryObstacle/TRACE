from __future__ import annotations

from collections import deque

from tgraph.core.graph import TGraph
from tgraph.operations.inspect.ports import port_owner_map


def find_path(graph: TGraph, *, source: str, target: str) -> dict:
    adjacency = _adjacency(graph)
    queue: deque[list[str]] = deque([[source]])
    seen = {source}
    while queue:
        path = queue.popleft()
        node = path[-1]
        if node == target:
            return {"reachable": True, "path": path}
        for neighbor in sorted(adjacency.get(node, set())):
            if neighbor in seen:
                continue
            seen.add(neighbor)
            queue.append([*path, neighbor])
    return {"reachable": False, "path": []}


def _adjacency(graph: TGraph) -> dict[str, set[str]]:
    owners = port_owner_map(graph)
    adjacency: dict[str, set[str]] = {node.id: set() for node in graph.nodes}
    for link in graph.links:
        node_a = link.from_node or owners.get(link.from_port)
        node_b = link.to_node or owners.get(link.to_port)
        if not node_a or not node_b:
            continue
        adjacency.setdefault(node_a, set()).add(node_b)
        adjacency.setdefault(node_b, set()).add(node_a)
    return adjacency

