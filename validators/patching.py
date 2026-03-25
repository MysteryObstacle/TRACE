from __future__ import annotations

from typing import Any

from tools.tgraph.ops.patch import PatchResult, patch


def apply_patch_result(graph: dict[str, Any], ops: list[dict[str, Any]]) -> PatchResult:
    return patch(graph, ops)


def apply_patch_ops(graph: dict[str, Any], ops: list[dict[str, Any]]) -> dict[str, Any]:
    result = apply_patch_result(graph, ops)
    if not result.ok or result.graph is None:
        raise ValueError(result.issues[0].message)
    return result.graph
