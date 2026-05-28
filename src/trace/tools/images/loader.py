from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


OPENSTACK_OBTAIN_IMAGE_IDS: tuple[str, ...] = (
    "almalinux_9",
    "alpine_3",
    "arch_linux",
    "dragonflybsd",
    "freebsd",
    "netbsd",
    "openbsd",
    "centos_stream_9",
    "centos_stream_10",
    "cirros",
    "debian_12",
    "fedora_40",
    "kali_linux",
    "windows_server_2019",
    "windows_server_2022",
    "windows_10",
    "opensuse_leap",
    "sles_15",
    "rhel_9",
    "rhel_8",
    "rocky_9",
    "ubuntu_22",
    "ubuntu_24",
)


class FlavorModel(BaseModel):
    vcpu: int = Field(ge=1)
    ram: int = Field(ge=128)
    disk: int = Field(ge=1)


class ImageEntryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    catalog_group: str
    node_types: list[str]
    roles: list[str]
    aliases: list[str]
    legacy_ids: list[str]
    default_flavor: FlavorModel
    maturity: str
    description: str
    family: str | None = None
    os_family: str | None = None
    os_version: str | None = None
    login_user: str | None = None
    cloud_init: bool | None = None
    cloudbase_init: bool | None = None
    requires_subscription: bool | None = None
    disk_formats: list[str] | None = None
    container_format: str | None = None
    hypervisor_hints: list[str] | None = None
    source_reference: str | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized or normalized.startswith("img_"):
            raise ValueError("image id must be lowercase snake_case without img_ prefix")
        return normalized


class ImageCatalogModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int
    catalog_name: str
    catalog_description: str | None = None
    images: list[ImageEntryModel]


def catalog_json_path() -> Path:
    return Path(__file__).resolve().parents[4] / "data" / "trace" / "image_catalog.v1.json"


def catalog_schema_path() -> Path:
    return Path(__file__).resolve().parents[4] / "data" / "trace" / "schemas" / "image_catalog.v1.schema.json"


@lru_cache(maxsize=1)
def load_catalog_model() -> ImageCatalogModel:
    payload = json.loads(catalog_json_path().read_text(encoding="utf-8"))
    return ImageCatalogModel.model_validate(payload)


@lru_cache(maxsize=1)
def _canonical_by_id() -> dict[str, dict[str, Any]]:
    return {item.id: item.model_dump(mode="python") for item in load_catalog_model().images}


@lru_cache(maxsize=1)
def _legacy_to_canonical() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in load_catalog_model().images:
        mapping[item.id] = item.id
        for legacy in item.legacy_ids:
            mapping[str(legacy).strip()] = item.id
    return mapping


def resolve_image_id(image_id: str) -> str:
    normalized = str(image_id or "").strip()
    if not normalized:
        raise KeyError("empty image id")
    resolved = _legacy_to_canonical().get(normalized)
    if resolved is None:
        raise KeyError(f"unknown image id: {image_id}")
    return resolved


def list_images(*, node_type: str | None = None) -> list[dict[str, Any]]:
    items = list(_canonical_by_id().values())
    if node_type:
        requested = str(node_type).strip().lower()
        items = [item for item in items if requested in {str(v).lower() for v in item["node_types"]}]
    return [_present_image(item) for item in sorted(items, key=lambda item: item["id"])]


def get_image(image_id: str) -> dict[str, Any]:
    canonical = resolve_image_id(image_id)
    item = _canonical_by_id().get(canonical)
    if item is None:
        raise KeyError(f"unknown image id: {image_id}")
    return _present_image(item)


def find_images(
    *,
    query: str | None = None,
    roles: list[str] | None = None,
    node_type: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in item.items() if key not in {"match_score", "match_reasons"}}
        for item in find_images_ranked(query=query, roles=roles, node_type=node_type, limit=limit)
    ]


def find_images_ranked(
    *,
    query: str | None = None,
    roles: list[str] | None = None,
    node_type: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    requested_roles = {str(item).strip().lower() for item in (roles or []) if str(item).strip()}
    requested_node_type = str(node_type or "").strip().lower()
    query_terms = [item for item in str(query or "").strip().lower().replace("-", " ").split() if item]
    scored: list[tuple[int, list[str], dict[str, Any]]] = []

    for item in _canonical_by_id().values():
        score, reasons = _match_score_with_reasons(
            item,
            query_terms=query_terms,
            roles=requested_roles,
            node_type=requested_node_type,
        )
        if score <= 0 and (query_terms or requested_roles or requested_node_type):
            continue
        scored.append((score, reasons, item))

    scored.sort(key=lambda pair: (-pair[0], pair[2]["id"]))
    normalized_limit = max(1, min(int(limit), 50))
    ranked: list[dict[str, Any]] = []
    for score, reasons, item in scored[:normalized_limit]:
        presented = _present_image(item)
        presented["match_score"] = score
        presented["match_reasons"] = reasons
        ranked.append(presented)
    return ranked


def catalog_summary_for_prompt(*, node_types: list[str] | None = None, max_entries: int = 40) -> str:
    allowed = {str(item).strip().lower() for item in (node_types or ["computer"]) if str(item).strip()}
    lines: list[str] = []
    for item in sorted(_canonical_by_id().values(), key=lambda row: row["id"]):
        item_types = {str(value).lower() for value in item["node_types"]}
        if allowed and not (item_types & allowed):
            continue
        os_family = item.get("os_family") or item.get("family") or item["catalog_group"]
        lines.append(f"- {item['id']}: {item['name']} ({os_family})")
        if len(lines) >= max_entries:
            break
    return (
        "Canonical image ids (use exact id + matching name in graph metadata):\n"
        + "\n".join(lines)
        + "\nUse list_images / find_images / get_image for full metadata."
    )


def openstack_guide_image_ids() -> list[str]:
    return [
        item.id
        for item in load_catalog_model().images
        if item.catalog_group == "openstack_image_guide"
    ]


def _match_score(
    item: dict[str, Any],
    *,
    query_terms: list[str],
    roles: set[str],
    node_type: str,
) -> int:
    score, _ = _match_score_with_reasons(item, query_terms=query_terms, roles=roles, node_type=node_type)
    return score


def _match_score_with_reasons(
    item: dict[str, Any],
    *,
    query_terms: list[str],
    roles: set[str],
    node_type: str,
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    item_roles = {str(role).lower() for role in item["roles"]}
    item_node_types = {str(value).lower() for value in item["node_types"]}
    haystack = " ".join(
        [
            str(item["id"]),
            str(item["name"]),
            " ".join(str(role) for role in item["roles"]),
            " ".join(str(alias) for alias in item["aliases"]),
            " ".join(str(legacy) for legacy in item.get("legacy_ids", [])),
        ]
    ).lower()

    if roles:
        overlap = roles & item_roles
        if not overlap:
            return 0, []
        for role in sorted(overlap):
            reasons.append(f"role:{role}")
        score += 10 * len(overlap)

    if node_type:
        if node_type not in item_node_types:
            return 0, []
        reasons.append(f"node_type:{node_type}")
        score += 4

    for term in query_terms:
        if term in haystack:
            reasons.append(f"term:{term}")
            score += 1

    if not roles and not node_type and not query_terms:
        return 1, ["catalog:browse"]
    return score, reasons


def _present_image(item: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(item)
    data["image"] = {"id": data["id"], "name": data["name"]}
    return data


def clear_catalog_cache() -> None:
    load_catalog_model.cache_clear()
    _canonical_by_id.cache_clear()
    _legacy_to_canonical.cache_clear()
