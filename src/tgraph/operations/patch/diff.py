from __future__ import annotations

from typing import Any


def empty_diff() -> dict[str, Any]:
    return {
        "nodes_added": [],
        "nodes_updated": [],
        "nodes_removed": [],
        "ports_added": [],
        "ports_updated": [],
        "ports_removed": [],
        "links_added": [],
        "links_removed": [],
        "stage_changed": False,
    }


def append_unique(target: list[str], value: str) -> None:
    if value not in target:
        target.append(value)

