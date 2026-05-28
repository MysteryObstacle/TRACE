from __future__ import annotations

import json
from typing import Any

from langchain.tools import tool
from pydantic import BaseModel, Field, field_validator

from trace.tools.images.loader import find_images as _find_images_raw
from trace.tools.images.loader import find_images_ranked, get_image, list_images


def coerce_string_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        raise ValueError("expected a list or string, got object")
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        if "," in text:
            return [part.strip() for part in text.split(",") if part.strip()]
        return [text]
    return [str(value).strip()] if str(value).strip() else None


class FindImagesInput(BaseModel):
    query: str | None = None
    roles: list[str] | None = None
    node_type: str | None = None
    limit: int = 10

    @field_validator("roles", mode="before")
    @classmethod
    def _coerce_roles(cls, value: Any) -> list[str] | None:
        return coerce_string_list(value)


class ListImagesInput(BaseModel):
    node_type: str | None = None
    limit: int = Field(default=50, ge=1, le=100)


class GetImageInput(BaseModel):
    image_id: str


def invoke_list_images(*, node_type: str | None = None, limit: int = 50) -> dict[str, Any]:
    images = list_images(node_type=node_type)
    normalized_limit = max(1, min(int(limit), 100))
    trimmed = images[:normalized_limit]
    return {
        "ok": True,
        "images": [
            {
                "id": item["id"],
                "name": item["name"],
                "roles": list(item["roles"]),
                "node_types": list(item["node_types"]),
                "default_flavor": dict(item["default_flavor"]),
            }
            for item in trimmed
        ],
        "total": len(images),
        "returned": len(trimmed),
    }


def invoke_find_images(
    *,
    query: str | None = None,
    roles: list[str] | None = None,
    node_type: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    coerced_roles = coerce_string_list(roles)
    ranked = find_images_ranked(query=query, roles=coerced_roles, node_type=node_type, limit=limit)
    interpretation = {
        "query": query,
        "roles": coerced_roles or [],
        "node_type": node_type,
    }
    if ranked:
        return {
            "ok": True,
            "images": ranked,
            "query_interpretation": interpretation,
            "suggestions": [],
        }
    return {
        "ok": True,
        "images": [],
        "query_interpretation": interpretation,
        "suggestions": _find_images_suggestions(query=query, roles=coerced_roles, node_type=node_type),
    }


def invoke_get_image(image_id: str) -> dict[str, Any]:
    try:
        record = get_image(image_id)
    except KeyError as exc:
        return {
            "ok": False,
            "error": {
                "code": "unknown_image_id",
                "message": str(exc),
                "field": "image_id",
            },
            "suggestions": [
                "Call list_images() to browse the catalog.",
                "Call find_images(query=..., roles=[...], node_type='computer') to search.",
            ],
        }
    return {"ok": True, **record}


def _find_images_suggestions(
    *,
    query: str | None,
    roles: list[str] | None,
    node_type: str | None,
) -> list[str]:
    suggestions: list[str] = ["Call list_images(node_type='computer') to browse all computer images."]
    if roles:
        suggestions.append("Retry find_images with fewer roles or a broader query string.")
    if query:
        suggestions.append("Try find_images with shorter query terms or omit roles/node_type filters.")
    if node_type and node_type != "computer":
        suggestions.append("Most deployment images target node_type='computer'.")
    return suggestions


def build_image_agent_tools() -> list[Any]:
    @tool("list_images", args_schema=ListImagesInput)
    def list_images_tool(node_type: str | None = None, limit: int = 50) -> dict[str, Any]:
        """Browse the image catalog. Optional node_type filter (e.g. computer). Returns compact image records."""

        return invoke_list_images(node_type=node_type, limit=limit)

    @tool("find_images", args_schema=FindImagesInput)
    def find_images_tool(
        query: str | None = None,
        roles: list[str] | None = None,
        node_type: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Search the image catalog by query, roles, or node_type. Returns ranked matches with match_reasons."""

        return invoke_find_images(query=query, roles=roles, node_type=node_type, limit=limit)

    @tool("get_image", args_schema=GetImageInput)
    def get_image_tool(image_id: str) -> dict[str, Any]:
        """Look up one image by canonical or legacy id."""

        return invoke_get_image(image_id)

    return [list_images_tool, find_images_tool, get_image_tool]


# Backward-compatible aliases for repair_tools imports.
_FindImagesInput = FindImagesInput
_GetImageInput = GetImageInput
_ListImagesInput = ListImagesInput
