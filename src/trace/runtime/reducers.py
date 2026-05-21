from __future__ import annotations

from copy import deepcopy
from typing import Any


def merge_run_state(current: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(current)

    for field in ("status", "current_stage", "error", "config_snapshot", "run_id", "intent"):
        if field in update:
            merged[field] = deepcopy(update[field])

    merged["artifacts"] = _merge_dict(merged.get("artifacts", {}), update.get("artifacts", {}))
    merged["attempt_counters"] = _merge_dict(merged.get("attempt_counters", {}), update.get("attempt_counters", {}))
    merged["stage_reports"] = _merge_dict(merged.get("stage_reports", {}), update.get("stage_reports", {}))
    merged["events"] = [*merged.get("events", []), *deepcopy(update.get("events", []))]
    return merged


def _merge_dict(current: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    return {**deepcopy(current), **deepcopy(update)}
