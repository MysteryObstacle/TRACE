from __future__ import annotations

import json
from typing import Any

from trace.stages.repair_tools import _derive_produced_files


LEDGER_WINDOW = 2


def format_section(name: str, value: Any) -> str:
    if isinstance(value, (dict, list, bool)):
        return f"[{name}]\n{json.dumps(value, indent=2, ensure_ascii=False)}"
    return f"[{name}]\n{value}"


def summarize_recent_repair_ledger(repair_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for item in repair_history[-LEDGER_WINDOW:]:
        summary.append(
            {
                "round": item.get("round"),
                "issue_kinds_before": item.get("issue_kinds_before", []),
                "resolved_issue_kinds": item.get("resolved_issue_kinds", []),
                "remaining_issue_kinds": item.get("remaining_issue_kinds", []),
                "new_issue_kinds": item.get("new_issue_kinds", []),
                "attempted_actions": item.get("attempted_actions", []),
                "failed_actions": item.get("failed_actions", []),
                "produced_files": item.get("produced_files", []),
            }
        )
    return summary


def build_repair_ledger_entry(
    *,
    round_index: int,
    issues_before: dict[str, Any],
    issues_after: dict[str, Any],
    attempted_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    before = issue_kinds(issues_before)
    after = issue_kinds(issues_after)
    before_set = set(before)
    after_set = set(after)
    failed_actions = [item for item in attempted_actions if item.get("ok") is False]
    return {
        "round": round_index,
        "mode": "agent",
        "issue_count": len(issues_before.get("issues", [])),
        "issue_kinds_before": before,
        "resolved_issue_kinds": sorted(before_set - after_set),
        "remaining_issue_kinds": after,
        "new_issue_kinds": sorted(after_set - before_set),
        "attempted_actions": attempted_actions,
        "failed_actions": failed_actions,
        "produced_files": _derive_produced_files(attempted_actions),
    }


def issue_kinds(report: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in report.get("issues", []):
        details = item.get("details") or {}
        issue_kind = str(details.get("issue_kind") or item.get("code") or "").strip()
        if not issue_kind or issue_kind in seen:
            continue
        seen.add(issue_kind)
        ordered.append(issue_kind)
    return ordered


def extract_tool_attempts(agent_result: Any) -> list[dict[str, Any]]:
    if not isinstance(agent_result, dict):
        return []
    messages = agent_result.get("messages")
    if not isinstance(messages, list):
        return []

    pending: dict[str, dict[str, Any]] = {}
    attempts: list[dict[str, Any]] = []

    for message in messages:
        for call in _message_tool_calls(message):
            call_id = str(call.get("id") or "")
            if call_id:
                pending[call_id] = {
                    "tool": str(call.get("name") or ""),
                    "args": call.get("args") if isinstance(call.get("args"), dict) else {},
                }

        tool_name = _message_tool_name(message)
        if not tool_name:
            continue
        tool_call_id = _message_tool_call_id(message)
        parsed_result = _parse_tool_result(_message_content(message))
        attempt = {
            "tool": tool_name,
            "args": pending.get(tool_call_id, {}).get("args", {}),
        }
        ok = _tool_result_ok(parsed_result)
        if ok is not None:
            attempt["ok"] = ok
        if isinstance(parsed_result, dict):
            attempt["result"] = parsed_result
        attempts.append(attempt)

    return attempts


def _message_tool_calls(message: Any) -> list[dict[str, Any]]:
    if isinstance(message, dict):
        value = message.get("tool_calls")
        return value if isinstance(value, list) else []
    value = getattr(message, "tool_calls", None)
    return value if isinstance(value, list) else []


def _message_tool_name(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("name") or "")
    return str(getattr(message, "name", "") or "")


def _message_tool_call_id(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("tool_call_id") or "")
    return str(getattr(message, "tool_call_id", "") or "")


def _message_content(message: Any) -> Any:
    if isinstance(message, dict):
        return message.get("content")
    return getattr(message, "content", None)


def _parse_tool_result(content: Any) -> Any:
    if not isinstance(content, str):
        return content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return content


def _tool_result_ok(result: Any) -> bool | None:
    if not isinstance(result, dict):
        return None
    if "ok" in result:
        return bool(result.get("ok"))
    return None
