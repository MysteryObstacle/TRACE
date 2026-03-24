from __future__ import annotations

from typing import Any

from app.contracts import ArtifactSelector
from artifacts.store import ArtifactStore


def resolve_inputs(store: ArtifactStore, selectors: list[ArtifactSelector]) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    for selector in selectors:
        item = store.read_latest(selector.stage, selector.name)
        if item is None:
            if selector.required:
                raise FileNotFoundError(f'Missing required artifact: {selector.stage}.{selector.name}')
            continue

        _, data = item
        resolved[f'{selector.stage}.{selector.name}'] = data
    return resolved
