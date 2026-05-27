from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trace.stages.ground.schemas import LOGICAL_CONSTRAINTS_PATH
from trace.stages.logical.state import LogicalState
from trace.stages.prompt_contracts import load_tgraph_contract_for
from trace.stages.repair_tools import StageRepairTools, _derive_produced_files
from trace.stages.support_files import load_constraint_entries


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "repair.md"
MAX_REACT_STEPS = 12
LEDGER_WINDOW = 2


def repair_node(state: LogicalState, role_client) -> LogicalState:
    prior_ledger = list(state.get("repair_history", []))
    repair_tools = StageRepairTools(
        state["draft_artifact"],
        support_files=state.get("support_files", {}),
        support_file_root=state.get("support_file_root"),
        mutation_index_seed=len(prior_ledger) + 2,
    )
    messages = _build_repair_messages(
        system_prompt=PROMPT_PATH.read_text(encoding="utf-8").strip(),
        tgraph_contract=load_tgraph_contract_for("logical_repair"),
        evaluation_report=state["evaluation_report"],
        current_topology=repair_tools.inspect_graph(view="summary"),
        logical_constraints=load_constraint_entries(
            support_files=state.get("support_files", {}),
            constraint_files=state["draft_artifact"].get("constraint_files", {})
            or state.get("ground_artifact", {}).get("constraint_files", {}),
            scope="logical",
            default_path=LOGICAL_CONSTRAINTS_PATH,
        ),
        constraint_files=state["draft_artifact"].get("constraint_files", {}),
        checkpoint_files=state["draft_artifact"].get("checkpoint_files", {}),
        recent_repair_ledger=_summarize_recent_repair_ledger(prior_ledger),
    )

    agent_result = role_client.invoke_agent(
        role_name="logical_repair",
        messages=messages,
        tools=repair_tools.as_agent_tools(),
        max_react_steps=MAX_REACT_STEPS,
    )

    post_repair_report = repair_tools.validate_graph()
    ledger_entry = _build_repair_ledger_entry(
        round_index=len(prior_ledger) + 1,
        issues_before=state["evaluation_report"],
        issues_after=post_repair_report,
        attempted_actions=_extract_tool_attempts(agent_result),
    )
    next_attempt = state["attempt"] + 1

    return {
        "draft_artifact": repair_tools.artifact_state(),
        "support_files": repair_tools.support_files(),
        "messages": _extract_messages(agent_result),
        "attempt": next_attempt,
        "repair_history": [ledger_entry],
        "events": [{"type": "logical.repair.completed", "attempt": next_attempt}],
    }


def _build_repair_messages(
    *,
    system_prompt: str,
    tgraph_contract: str,
    evaluation_report: dict[str, Any],
    current_topology: dict[str, Any],
    logical_constraints: list[dict[str, Any]],
    constraint_files: dict[str, str],
    checkpoint_files: dict[str, str],
    recent_repair_ledger: list[dict[str, Any]],
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": "TGraph contract for this repair round:\n\n" + tgraph_contract},
        {"role": "human", "content": "Use file-backed TGraph tools to repair the logical artifact."},
        {"role": "human", "content": _format_section("evaluation_report", evaluation_report)},
        {"role": "human", "content": _format_section("evaluation_report_is_latest", True)},
        {"role": "human", "content": _format_section("current_topology", current_topology)},
        {"role": "human", "content": _format_section("logical_constraints", logical_constraints)},
        {"role": "human", "content": _format_section("constraint_files", constraint_files)},
        {"role": "human", "content": _format_section("checkpoint_files", checkpoint_files)},
        {
            "role": "human",
            "content": _format_section(
                "repair_file_guidance",
                {
                    "graph_mutation": "write logical/mutations/attempt_N.py with mutate(tgraph), then execute_mutation_file.",
                    "checkpoint_repair": "read and rewrite logical/checkpoints.py only when the issue is in the checkpoint function.",
                },
            ),
        },
        {"role": "human", "content": _format_section("recent_repair_ledger", recent_repair_ledger)},
    ]


def _format_section(name: str, value: Any) -> str:
    if isinstance(value, (dict, list, bool)):
        return f"[{name}]\n{json.dumps(value, indent=2, ensure_ascii=False)}"
    return f"[{name}]\n{value}"


def _extract_messages(agent_result: Any) -> list[dict[str, Any]]:
    if isinstance(agent_result, dict):
        messages = agent_result.get("messages")
        if isinstance(messages, list):
            return [item for item in messages if isinstance(item, dict) and item.get("role")]
    return []


def _summarize_recent_repair_ledger(repair_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _build_repair_ledger_entry(
    *,
    round_index: int,
    issues_before: dict[str, Any],
    issues_after: dict[str, Any],
    attempted_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    before = _issue_kinds(issues_before)
    after = _issue_kinds(issues_after)
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


def _issue_kinds(report: dict[str, Any]) -> list[str]:
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


def _extract_tool_attempts(agent_result: Any) -> list[dict[str, Any]]:
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
