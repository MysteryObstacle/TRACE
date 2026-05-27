from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict


class LogicalState(TypedDict, total=False):
    ground_artifact: dict[str, Any]
    attempt: int
    max_attempts: int
    author_output: dict[str, Any]
    draft_artifact: dict[str, Any]
    logical_artifact: dict[str, Any]
    evaluation_report: dict[str, Any]
    repair_history: Annotated[list[dict[str, Any]], add]
    messages: list[dict[str, str]]
    events: Annotated[list[dict[str, Any]], add]
    support_files: dict[str, str]
    support_file_root: str
    result: dict[str, Any]
    error: dict[str, Any] | None
    escalation_report: dict[str, Any] | None
