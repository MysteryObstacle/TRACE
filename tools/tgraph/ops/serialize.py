from __future__ import annotations

import json
from typing import Any

from tools.tgraph.model import SUPPORTED_PROFILES, TGraph, ensure_tgraph


def serialize(graph: TGraph | dict[str, Any], profile: str) -> dict[str, Any]:
    if profile not in SUPPORTED_PROFILES:
        raise ValueError(f"unsupported_export_profile:{profile}")

    model = ensure_tgraph(graph)
    if model.profile != profile:
        raise ValueError(f"export_profile_mismatch:{model.profile}->{profile}")

    return model.model_dump(mode="json")


def export_tgraph_json(graph: TGraph | dict[str, Any], profile: str) -> str:
    payload = serialize(graph, profile=profile)
    try:
        return json.dumps(payload, sort_keys=True)
    except TypeError as exc:
        raise ValueError("export_non_serializable_value") from exc
