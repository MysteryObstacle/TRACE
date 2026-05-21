from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

KNOWN_GRAPH_OPS = {
    "ensure_node",
    "ensure_port",
    "ensure_link",
    "remove_node",
    "remove_port",
    "remove_link",
    "set_stage",
}


class TGraphPatch(BaseModel):
    graph_patch: list[dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "PatchParseResult":
        from tgraph.operations.patch.result import PatchParseResult

        if not isinstance(payload, dict):
            return PatchParseResult(ok=False, error={"code": "patch_schema_error", "message": "patch must be an object"})
        ops = payload.get("graph_patch", [])
        if not isinstance(ops, list):
            return PatchParseResult(ok=False, error={"code": "patch_schema_error", "message": "graph_patch must be a list"})
        for op in ops:
            if not isinstance(op, dict):
                return PatchParseResult(ok=False, error={"code": "patch_schema_error", "message": "graph_patch items must be objects"})
            name = op.get("op")
            if name not in KNOWN_GRAPH_OPS:
                return PatchParseResult(ok=False, error={"code": "patch_schema_error", "message": f"unknown graph op: {name}"})
        return PatchParseResult(ok=True, patch=cls(graph_patch=ops))

