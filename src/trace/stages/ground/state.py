from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict


class GroundState(TypedDict, total=False):
    intent: str
    grounding_checks: dict[str, Any]
    attempt: int
    max_attempts: int
    status: str
    draft_artifact: dict[str, Any]
    evaluation_report: dict[str, Any]
    messages: list[dict[str, str]]
    retry_history: Annotated[list[dict[str, Any]], add]
    events: Annotated[list[dict[str, Any]], add]
    support_files: dict[str, str]
    support_file_root: str
    result: dict[str, Any]
    error: dict[str, Any] | None
