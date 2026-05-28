from __future__ import annotations

import json
from typing import Any

from trace.tools.images.loader import (
    OPENSTACK_OBTAIN_IMAGE_IDS,
    catalog_summary_for_prompt,
    find_images,
    get_image,
    list_images,
    load_catalog_model,
    resolve_image_id,
)


def image_catalog_prompt() -> str:
    payload = [
        {
            "image": {"id": item["id"], "name": item["name"]},
            "roles": list(item["roles"]),
            "node_types": list(item["node_types"]),
            "aliases": list(item["aliases"]),
            "default_flavor": dict(item["default_flavor"]),
        }
        for item in list_images()
    ]
    return (
        "Use these exact image.id values and matching image.name values. "
        "Do not invent image ids or image names.\n"
        + json.dumps(payload, indent=2, ensure_ascii=False)
    )


__all__ = [
    "OPENSTACK_OBTAIN_IMAGE_IDS",
    "catalog_summary_for_prompt",
    "find_images",
    "get_image",
    "image_catalog_prompt",
    "list_images",
    "load_catalog_model",
    "resolve_image_id",
]
