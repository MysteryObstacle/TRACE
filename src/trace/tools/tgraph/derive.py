from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from trace.tools.tgraph.model import LOGICAL_V1, TAAL_DEFAULT_V1


_PATTERN_RE = re.compile(r"^(?P<prefix>[A-Za-z][A-Za-z0-9_-]*?)\[(?P<start>\d+)\.\.(?P<end>\d+)\]$")


def expand_node_patterns(patterns: list[str]) -> list[str]:
    expanded: list[str] = []
    for pattern in patterns:
        match = _PATTERN_RE.match(pattern)
        if match is None:
            expanded.append(pattern)
            continue
        start = int(match.group("start"))
        end = int(match.group("end"))
        prefix = match.group("prefix")
        if end < start:
            raise ValueError(f"invalid pattern range: {pattern}")
        expanded.extend(f"{prefix}{index}" for index in range(start, end + 1))
    return expanded


def expand_node_groups(node_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for group in node_groups:
        node_type = group.get("type", "computer")
        members = [str(member) for member in group.get("members", []) or []]
        for node_id in expand_node_patterns(members):
            expanded.append(
                {
                    "id": node_id,
                    "type": node_type,
                    "label": node_id,
                }
            )
    return expanded


def build_logical_skeleton(expanded_nodes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "profile": LOGICAL_V1,
        "nodes": [
            {
                "id": item["id"],
                "type": item.get("type", "computer"),
                "label": item.get("label", item["id"]),
                "ports": [],
                "image": None,
                "flavor": None,
            }
            for item in expanded_nodes
        ],
        "links": [],
    }


def build_physical_graph(logical_graph: dict[str, Any]) -> dict[str, Any]:
    graph = deepcopy(logical_graph)
    graph["profile"] = TAAL_DEFAULT_V1
    graph.setdefault("nodes", [])
    graph.setdefault("links", [])
    return graph

