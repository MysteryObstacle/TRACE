from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from trace.stages.physical.nodes.validator import _validate_physical_artifact
from trace.stages.physical.state import PhysicalState
from trace.tools.images.catalog import image_catalog_prompt
from trace.tools.tgraph.protocol import BoundTGraphTools
from trace.tools.tgraph.prompting import load_tgraph_contract_for


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "repair.md"
MAX_TOOL_CALLS = 12
LEDGER_WINDOW = 2


def repair_node(state: PhysicalState, role_client) -> PhysicalState:
    prior_ledger = list(state.get("repair_history", []))
    authored_checkpoints = state["draft_artifact"].get("physical_checkpoints", [])
    authored_script = state["draft_artifact"].get("physical_validator_script")
    bound_tools = BoundTGraphTools.from_json(
        state["draft_artifact"]["tgraph_physical"],
        graph_field="tgraph_physical",
        checkpoints_field="physical_checkpoints",
        validator_script_field="physical_validator_script",
        checkpoints=authored_checkpoints,
        validator_script=authored_script,
        constraints=state.get("ground_artifact", {}).get("physical_constraints", []),
    )
    candidate_checkpoints = _select_candidate_checkpoints(
        authored_checkpoints,
        evaluation_report=state["evaluation_report"],
        limit=8,
    )
    messages = _build_repair_messages(
        system_prompt=PROMPT_PATH.read_text(encoding="utf-8").strip(),
        tgraph_contract=load_tgraph_contract_for("physical_repair"),
        image_catalog=image_catalog_prompt(),
        evaluation_report=state["evaluation_report"],
        current_topology=bound_tools.topology_view(),
        logical_topology=state["logical_artifact"]["tgraph_logical"],
        physical_constraints=state.get("ground_artifact", {}).get("physical_constraints", []),
        candidate_checkpoints=candidate_checkpoints,
        recent_repair_ledger=_summarize_recent_repair_ledger(prior_ledger),
        authored_checkpoint_count=len(authored_checkpoints),
        physical_validator_script=authored_script,
    )

    agent_result = role_client.invoke_agent(
        role_name="physical_repair",
        messages=messages,
        tools=bound_tools.tools(),
        max_tool_calls=MAX_TOOL_CALLS,
    )

    state["draft_artifact"] = {
        **state["draft_artifact"],
        **bound_tools.artifact_state(),
    }
    state["messages"] = _extract_messages(agent_result)
    post_repair_report = _validate_physical_artifact(
        artifact=state["draft_artifact"],
        logical_graph=state["logical_artifact"]["tgraph_logical"],
        author_output=state.get("author_output", {}),
        physical_constraints=state.get("ground_artifact", {}).get("physical_constraints", []),
    )
    ledger_entry = _build_repair_ledger_entry(
        round_index=len(prior_ledger) + 1,
        issues_before=state["evaluation_report"],
        issues_after=post_repair_report,
        attempted_actions=_extract_tool_attempts(agent_result),
    )
    state["attempt"] += 1
    state["repair_history"] = [*prior_ledger, ledger_entry]
    state["events"] = [*state.get("events", []), {"type": "physical.repair.completed", "attempt": state["attempt"]}]
    return state


def _build_repair_messages(
    *,
    system_prompt: str,
    tgraph_contract: str,
    image_catalog: str,
    evaluation_report: dict[str, Any],
    current_topology: dict[str, Any],
    logical_topology: dict[str, Any],
    physical_constraints: list[dict[str, Any]],
    candidate_checkpoints: list[dict[str, Any]],
    recent_repair_ledger: list[dict[str, Any]],
    authored_checkpoint_count: int,
    physical_validator_script: str | None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "system",
            "content": "TGraph contract for this repair round:\n\n" + tgraph_contract,
        },
        {
            "role": "system",
            "content": "Image catalog for this repair round:\n\n" + image_catalog,
        },
        {
            "role": "human",
            "content": "Use the provided node/link TGraph tools to repair the physical artifact while preserving logical topology.",
        },
        {
            "role": "human",
            "content": _format_section("evaluation_report", evaluation_report),
        },
        {
            "role": "human",
            "content": _format_section("evaluation_report_is_latest", True),
        },
        {
            "role": "human",
            "content": _format_section("current_topology", current_topology),
        },
        {
            "role": "human",
            "content": _format_section("logical_topology", logical_topology),
        },
        {
            "role": "human",
            "content": _format_section("physical_constraints", physical_constraints),
        },
        {
            "role": "human",
            "content": _format_section("candidate_checkpoints", candidate_checkpoints),
        },
        {
            "role": "human",
            "content": _format_section(
                "checkpoint_lookup_guidance",
                {
                    "authored_checkpoint_count": authored_checkpoint_count,
                    "candidate_checkpoint_count": len(candidate_checkpoints),
                    "message": "If candidate_checkpoints are insufficient, use find_checkpoints or get_checkpoint.",
                },
            ),
        },
        {
            "role": "human",
            "content": _format_section("recent_repair_ledger", recent_repair_ledger),
        },
    ]
    if physical_validator_script:
        messages.append(
            {
                "role": "human",
                "content": _format_section("physical_validator_script", physical_validator_script),
            }
        )
    return messages


def _format_section(name: str, value: Any) -> str:
    if isinstance(value, (dict, list, bool)):
        return f"[{name}]\n{json.dumps(value, indent=2, ensure_ascii=False)}"
    return f"[{name}]\n{value}"


def _select_candidate_checkpoints(
    checkpoints: list[dict[str, Any]],
    *,
    evaluation_report: dict[str, Any],
    limit: int,
) -> list[dict[str, Any]]:
    signals = _checkpoint_repair_signals(evaluation_report)
    scored: list[tuple[int, dict[str, Any]]] = []
    for checkpoint in checkpoints:
        score = _score_checkpoint_candidate(checkpoint, signals)
        if score <= 0:
            continue
        scored.append((score, checkpoint))

    scored.sort(key=lambda item: (-item[0], str(item[1].get("id") or "")))
    selected = [dict(item) for _, item in scored[:limit]]
    if selected:
        return selected
    return [dict(item) for item in checkpoints[:limit]]


def _checkpoint_repair_signals(evaluation_report: dict[str, Any]) -> dict[str, set[str]]:
    node_ids: set[str] = set()
    cidrs: set[str] = set()
    constraint_ids: set[str] = set()
    free_terms: set[str] = set()

    for issue in evaluation_report.get("issues", []):
        provenance = issue.get("provenance") or {}
        check_id = str(provenance.get("check_id") or "").strip()
        if check_id:
            constraint_ids.add(check_id)
        for constraint_id in provenance.get("constraint_ids") or []:
            token = str(constraint_id).strip()
            if token:
                constraint_ids.add(token)
        for target in issue.get("targets") or []:
            token = str(target).strip()
            if not token:
                continue
            if ":" in token:
                prefix, raw_value = token.split(":", 1)
                if prefix in {"node", "port", "link", "checkpoint"}:
                    node_ids.update(_extract_node_ids(raw_value))
                    if prefix == "checkpoint":
                        constraint_ids.add(raw_value)
                else:
                    node_ids.update(_extract_node_ids(token))
            else:
                node_ids.update(_extract_node_ids(token))
        message = str(issue.get("message") or "")
        node_ids.update(_extract_node_ids(message))
        cidrs.update(re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}/\d{1,2}\b", message))
        free_terms.update(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", message))

    return {
        "node_ids": node_ids,
        "cidrs": cidrs,
        "constraint_ids": constraint_ids,
        "free_terms": {item.lower() for item in free_terms},
    }


def _extract_node_ids(text: str) -> set[str]:
    matches = re.findall(r"\b[A-Z][A-Z0-9_]+\b|\b[A-Za-z]+[0-9_]+\b", text)
    return {item for item in matches if not item.startswith("checkpoint")}


def _score_checkpoint_candidate(checkpoint: dict[str, Any], signals: dict[str, set[str]]) -> int:
    haystack = _checkpoint_text(checkpoint)
    lowered = haystack.lower()
    score = 0

    for node_id in signals["node_ids"]:
        if node_id and node_id in haystack:
            score += 5
    for cidr in signals["cidrs"]:
        if cidr and cidr in haystack:
            score += 5
    for constraint_id in signals["constraint_ids"]:
        if constraint_id and constraint_id in haystack:
            score += 3
    for term in signals["free_terms"]:
        if term and term in lowered:
            score += 1
    return score


def _checkpoint_text(checkpoint: dict[str, Any]) -> str:
    return " ".join(
        [
            str(checkpoint.get("id") or ""),
            str(checkpoint.get("func") or ""),
            str(checkpoint.get("description") or ""),
            " ".join(str(item) for item in checkpoint.get("constraint_ids") or []),
            _flatten_value(checkpoint.get("args") or {}),
        ]
    ).strip()


def _flatten_value(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten_value(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_value(item) for item in value)
    return str(value)


def _extract_messages(agent_result: Any) -> list[dict[str, Any]]:
    if isinstance(agent_result, dict):
        messages = agent_result.get("messages")
        if isinstance(messages, list):
            return messages
    return []


def _summarize_recent_repair_ledger(repair_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for item in repair_history[-LEDGER_WINDOW:]:
        summary.append(
            {
                "round": item.get("round"),
                "issue_codes_before": item.get("issue_codes_before", []),
                "resolved_issue_codes": item.get("resolved_issue_codes", []),
                "remaining_issue_codes": item.get("remaining_issue_codes", []),
                "new_issue_codes": item.get("new_issue_codes", []),
                "attempted_actions": item.get("attempted_actions", []),
                "failed_actions": item.get("failed_actions", []),
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
    before_codes = _issue_codes(issues_before)
    after_codes = _issue_codes(issues_after)
    before_set = set(before_codes)
    after_set = set(after_codes)
    failed_actions = [item for item in attempted_actions if item.get("ok") is False]
    return {
        "round": round_index,
        "mode": "agent",
        "issue_count": len(issues_before.get("issues", [])),
        "issue_codes_before": before_codes,
        "resolved_issue_codes": sorted(before_set - after_set),
        "remaining_issue_codes": after_codes,
        "new_issue_codes": sorted(after_set - before_set),
        "attempted_actions": attempted_actions,
        "failed_actions": failed_actions,
    }


def _issue_codes(report: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in report.get("issues", []):
        code = str(item.get("code") or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        ordered.append(code)
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
        tool_calls = _message_tool_calls(message)
        for call in tool_calls:
            call_id = str(call.get("id") or "")
            if not call_id:
                continue
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
