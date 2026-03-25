from __future__ import annotations

from copy import deepcopy
from typing import Any


def build_logical_skeleton(node_ids: list[str]) -> dict[str, Any]:
    return {
        'profile': 'logical.v1',
        'nodes': [_default_node(node_id) for node_id in node_ids],
        'links': [],
    }


def build_physical_skeleton(logical_graph: dict[str, Any]) -> dict[str, Any]:
    graph = deepcopy(logical_graph)
    graph['profile'] = 'taal.default.v1'
    graph.setdefault('nodes', [])
    graph.setdefault('links', [])
    return graph


def summarize_patch_ops(patch_ops: list[dict[str, Any]] | None) -> dict[str, Any]:
    ops = patch_ops or []
    return {
        'op_count': len(ops),
        'ops': [str(item.get('op', 'unknown')) for item in ops],
    }


def _default_node(node_id: str) -> dict[str, Any]:
    return {
        'id': node_id,
        'type': 'computer',
        'label': node_id,
        'ports': [],
        'image': None,
        'flavor': None,
    }
