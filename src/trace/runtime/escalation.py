from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from tgraph.operations.validate.escalation_kinds import ESCALATION_ISSUE_KINDS

ESCALATION_TO_GROUND_KINDS = ESCALATION_ISSUE_KINDS


def extract_escalation_issues(report: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not report:
        return []
    matches: list[dict[str, Any]] = []
    for issue in report.get("issues", []) or []:
        details = issue.get("details") if isinstance(issue, dict) else None
        if not isinstance(details, dict):
            continue
        if details.get("issue_kind") in ESCALATION_TO_GROUND_KINDS:
            matches.append(issue)
    return matches


def build_escalation_report(
    *,
    stage_id: str,
    report: dict[str, Any],
    partial_artifact: dict[str, Any] | None,
    attempt: int,
) -> dict[str, Any]:
    return {
        "source_stage": stage_id,
        "attempt_at_escalation": attempt,
        "issues": list(report.get("issues", []) or []),
        "notes": list(report.get("notes", []) or []),
        "partial_artifact": partial_artifact or {},
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
