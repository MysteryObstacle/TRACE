from __future__ import annotations

from copy import deepcopy
from typing import Any


def apply_patch_ops(graph: dict[str, Any], ops: list[dict[str, Any]]) -> dict[str, Any]:
    updated = deepcopy(graph)
    updated.setdefault('nodes', [])
    updated.setdefault('edges', [])

    for op in ops:
        op_name = op['op']
        if op_name == 'add_node':
            updated['nodes'].append(op['value'])
            continue
        if op_name == 'add_edge':
            updated['edges'].append(op['value'])
            continue
        raise ValueError(f'Unsupported patch op: {op_name}')

    return updated
