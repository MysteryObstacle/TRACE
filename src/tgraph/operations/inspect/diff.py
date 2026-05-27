from __future__ import annotations

from typing import Any

from tgraph.core.graph import TGraph

_NODE_FIELDS = ("type", "label", "image", "flavor", "ports", "metadata")


def diff(current: TGraph, baseline: TGraph) -> dict[str, Any]:
    current_nodes = {node.id: node for node in current.nodes}
    baseline_nodes = {node.id: node for node in baseline.nodes}

    added = sorted(current_nodes.keys() - baseline_nodes.keys())
    removed = sorted(baseline_nodes.keys() - current_nodes.keys())

    changed: list[dict[str, Any]] = []
    unchanged = 0
    for node_id in sorted(current_nodes.keys() & baseline_nodes.keys()):
        cur = current_nodes[node_id].model_dump(mode="json")
        base = baseline_nodes[node_id].model_dump(mode="json")
        diff_fields = sorted({field for field in _NODE_FIELDS if cur.get(field) != base.get(field)})
        if diff_fields:
            changed.append({"id": node_id, "fields_changed": diff_fields})
        else:
            unchanged += 1

    return {
        "added_nodes": added,
        "removed_nodes": removed,
        "changed_nodes": changed,
        "unchanged_count": unchanged,
    }
