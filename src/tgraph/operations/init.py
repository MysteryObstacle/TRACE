from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping

from tgraph.core.graph import TGraph

_PATTERN_RE = re.compile(r"^(?P<prefix>[A-Z][A-Z0-9_]*?)\[(?P<start>\d+)\.\.(?P<end>\d+)\]$")


def init_logical_skeleton(node_groups: list[dict[str, Any]]) -> TGraph:
    return TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": _expand_node_groups(node_groups),
            "links": [],
        }
    )


def init_physical_skeleton(
    logical_graph: TGraph | dict[str, Any],
    *,
    defaults_by_type: Mapping[str, Mapping[str, Any]] | None = None,
) -> TGraph:
    source = logical_graph if isinstance(logical_graph, TGraph) else TGraph.model_validate(logical_graph)
    payload = deepcopy(source.model_dump(mode="json"))
    payload["stage"] = "physical"
    defaults = defaults_by_type or {}
    for node in payload.get("nodes", []):
        node_defaults = defaults.get(str(node.get("type")), {})
        if node.get("image") is None and "image" in node_defaults:
            node["image"] = deepcopy(node_defaults.get("image"))
        if node.get("flavor") is None and "flavor" in node_defaults:
            node["flavor"] = deepcopy(node_defaults.get("flavor"))
    return TGraph.model_validate(payload)


def _expand_node_groups(node_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for group in node_groups:
        node_type = str(group.get("type", "computer"))
        for node_id in _expand_node_patterns([str(member) for member in group.get("members", []) or []]):
            nodes.append({"id": node_id, "type": node_type, "label": node_id, "ports": []})
    return nodes


def _expand_node_patterns(patterns: list[str]) -> list[str]:
    expanded: list[str] = []
    for pattern in patterns:
        match = _PATTERN_RE.match(pattern)
        if match is None:
            expanded.append(pattern)
            continue
        start = int(match.group("start"))
        end = int(match.group("end"))
        if end < start:
            raise ValueError(f"invalid pattern range: {pattern}")
        prefix = match.group("prefix")
        expanded.extend(f"{prefix}{index}" for index in range(start, end + 1))
    return expanded
