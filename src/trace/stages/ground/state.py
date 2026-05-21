from __future__ import annotations

from typing import Any, TypedDict


class GroundState(TypedDict, total=False):
    intent: str
    grounding_checks: dict[str, Any]
    attempt: int
    max_attempts: int
    status: str
    draft_artifact: dict[str, Any]
    evaluation_report: dict[str, Any]
    messages: list[dict[str, str]]
    retry_history: list[dict[str, Any]]
    events: list[dict[str, Any]]
    result: dict[str, Any]
    next_action: str
    error: dict[str, Any] | None
