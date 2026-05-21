from __future__ import annotations

from typing import Any, TypedDict


class LogicalState(TypedDict, total=False):
    ground_artifact: dict[str, Any]
    attempt: int
    max_attempts: int
    author_output: dict[str, Any]
    draft_artifact: dict[str, Any]
    working_graph: dict[str, Any]
    evaluation_report: dict[str, Any]
    repair_history: list[dict[str, Any]]
    messages: list[dict[str, str]]
    events: list[dict[str, Any]]
    next_action: str
    result: dict[str, Any]
    error: dict[str, Any] | None
