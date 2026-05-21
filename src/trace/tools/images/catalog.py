from __future__ import annotations

import json
from copy import deepcopy
from typing import Any


IMAGE_CATALOG: list[dict[str, Any]] = [
    {
        "id": "img_pfsense",
        "name": "pfsense",
        "roles": ["firewall"],
        "node_types": ["computer"],
        "aliases": ["firewall", "firewall appliance", "pfsense", "packet filter"],
        "default_flavor": {"vcpu": 2, "ram": 2048, "disk": 10},
    },
    {
        "id": "img_linux_internet_gateway",
        "name": "linux-internet-gateway",
        "roles": ["internet_gateway", "linux_gateway"],
        "node_types": ["computer"],
        "aliases": ["internet", "internet gateway", "simulated internet", "linux internet gateway", "wan gateway"],
        "default_flavor": {"vcpu": 1, "ram": 512, "disk": 5},
    },
    {
        "id": "img_ubuntu_22",
        "name": "ubuntu-22.04",
        "roles": ["linux_host", "web_server", "admin_workstation", "workstation"],
        "node_types": ["computer"],
        "aliases": ["ubuntu", "linux", "web", "server", "admin", "workstation", "pc"],
        "default_flavor": {"vcpu": 2, "ram": 2048, "disk": 20},
    },
    {
        "id": "img_tiny_linux",
        "name": "tiny-linux",
        "roles": ["linux_host", "lightweight_host"],
        "node_types": ["computer"],
        "aliases": ["tiny linux", "lightweight", "small host"],
        "default_flavor": {"vcpu": 1, "ram": 512, "disk": 5},
    },
    {
        "id": "img_openplc",
        "name": "OpenPLC",
        "roles": ["plc_runtime"],
        "node_types": ["computer"],
        "aliases": ["plc", "openplc", "plc runtime"],
        "default_flavor": {"vcpu": 1, "ram": 512, "disk": 5},
    },
    {
        "id": "img_scada",
        "name": "scada-workstation",
        "roles": ["scada"],
        "node_types": ["computer"],
        "aliases": ["scada", "scada capability", "supervisory control"],
        "default_flavor": {"vcpu": 2, "ram": 4096, "disk": 20},
    },
    {
        "id": "img_hmi",
        "name": "hmi-workstation",
        "roles": ["hmi"],
        "node_types": ["computer"],
        "aliases": ["hmi", "hmi capability", "operator workstation"],
        "default_flavor": {"vcpu": 2, "ram": 2048, "disk": 20},
    },
    {
        "id": "img_industrial_historian",
        "name": "industrial-historian",
        "roles": ["industrial_historian"],
        "node_types": ["computer"],
        "aliases": ["historian", "industrial historian", "industrial historian capability", "process historian"],
        "default_flavor": {"vcpu": 2, "ram": 4096, "disk": 40},
    },
    {
        "id": "img_engineering_workstation",
        "name": "engineering-workstation",
        "roles": ["engineering_workstation"],
        "node_types": ["computer"],
        "aliases": ["engineering workstation", "engineering workstation capability", "engineer station"],
        "default_flavor": {"vcpu": 2, "ram": 4096, "disk": 20},
    },
    {
        "id": "img_router_linux",
        "name": "linux-router",
        "roles": ["router"],
        "node_types": ["router"],
        "aliases": ["router", "core router", "branch router", "linux router"],
        "default_flavor": {"vcpu": 2, "ram": 2048, "disk": 10},
    },
    {
        "id": "img_l2_switch",
        "name": "l2-switch",
        "roles": ["switch", "l2_switch"],
        "node_types": ["switch"],
        "aliases": ["switch", "l2 switch", "bridge"],
        "default_flavor": {"vcpu": 1, "ram": 512, "disk": 5},
    },
]


def list_images() -> list[dict[str, Any]]:
    return [_present_image(item) for item in IMAGE_CATALOG]


def get_image(image_id: str) -> dict[str, Any]:
    normalized = str(image_id or "").strip()
    for item in IMAGE_CATALOG:
        if item["id"] == normalized:
            return _present_image(item)
    raise KeyError(f"unknown image id: {image_id}")


def find_images(
    *,
    query: str | None = None,
    roles: list[str] | None = None,
    node_type: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    requested_roles = {str(item).strip().lower() for item in (roles or []) if str(item).strip()}
    requested_node_type = str(node_type or "").strip().lower()
    query_terms = [item for item in str(query or "").strip().lower().replace("-", " ").split() if item]
    scored: list[tuple[int, dict[str, Any]]] = []

    for item in IMAGE_CATALOG:
        score = _match_score(
            item,
            query_terms=query_terms,
            roles=requested_roles,
            node_type=requested_node_type,
        )
        if score <= 0 and (query_terms or requested_roles or requested_node_type):
            continue
        scored.append((score, item))

    scored.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    normalized_limit = max(1, min(int(limit), 50))
    return [_present_image(item) for _, item in scored[:normalized_limit]]


def image_catalog_prompt() -> str:
    payload = [
        {
            "image": {"id": item["id"], "name": item["name"]},
            "roles": list(item["roles"]),
            "node_types": list(item["node_types"]),
            "aliases": list(item["aliases"]),
            "default_flavor": dict(item["default_flavor"]),
        }
        for item in IMAGE_CATALOG
    ]
    return (
        "Use these exact image.id values and matching image.name values. "
        "Do not invent image ids or image names.\n"
        + json.dumps(payload, indent=2, ensure_ascii=False)
    )


def _match_score(
    item: dict[str, Any],
    *,
    query_terms: list[str],
    roles: set[str],
    node_type: str,
) -> int:
    score = 0
    item_roles = {str(role).lower() for role in item["roles"]}
    item_node_types = {str(value).lower() for value in item["node_types"]}
    haystack = " ".join(
        [
            str(item["id"]),
            str(item["name"]),
            " ".join(str(role) for role in item["roles"]),
            " ".join(str(alias) for alias in item["aliases"]),
        ]
    ).lower()

    if roles:
        overlap = roles & item_roles
        if not overlap:
            return 0
        score += 10 * len(overlap)

    if node_type:
        if node_type not in item_node_types:
            return 0
        score += 4

    for term in query_terms:
        if term in haystack:
            score += 1

    if not roles and not node_type and not query_terms:
        return 1
    return score


def _present_image(item: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(item)
    data["image"] = {"id": data["id"], "name": data["name"]}
    return data
