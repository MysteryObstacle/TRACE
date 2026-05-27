from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from trace.runtime.role_client import RoleClient


def build_messages(
    *,
    system_prompt: str,
    task: str,
    context_sections: dict[str, Any] | None = None,
    system_context_sections: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    lines = [task]
    for key, value in (context_sections or {}).items():
        lines.append(f"\n[{key}]\n{_format_context_value(value)}")
    messages = [{"role": "system", "content": system_prompt}]
    if system_context_sections:
        system_lines: list[str] = []
        for key, value in system_context_sections.items():
            system_lines.append(f"[{key}]\n{_format_context_value(value)}")
        messages.append({"role": "system", "content": "\n\n".join(system_lines).strip()})
    messages.append({"role": "human", "content": "\n".join(lines).strip()})
    return messages


def invoke_role(
    *,
    role_client: RoleClient,
    role_name: str,
    system_prompt_path: str | Path,
    task: str,
    context_sections: dict[str, Any] | None,
    system_context_sections: dict[str, Any] | None = None,
    schema: type[BaseModel],
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    messages = build_messages(
        system_prompt=Path(system_prompt_path).read_text(encoding="utf-8").strip(),
        task=task,
        context_sections=context_sections,
        system_context_sections=system_context_sections,
    )
    response = role_client.invoke_structured(role_name=role_name, messages=messages, schema=schema)
    if isinstance(response, BaseModel):
        payload = response.model_dump(mode="json")
    else:
        payload = schema.model_validate(response).model_dump(mode="json")
    return messages, payload


def require_stage_result(*, stage_id: str, final_state: dict[str, Any]) -> dict[str, Any]:
    if final_state.get("status") == "unsolvable":
        return {
            "status": "unsolvable",
            "evaluation_summary": final_state.get("evaluation_report"),
            "attempts_used": final_state.get("attempt", 1),
            "messages": final_state.get("messages", []),
            "tool_journal": [],
            _stage_history_name(stage_id): final_state.get(_stage_history_name(stage_id), []),
            "events": final_state.get("events", []),
            "support_files": final_state.get("support_files", {}),
            "unsolvable_notes": final_state.get("unsolvable_notes", []),
        }

    if "result" in final_state:
        result = final_state["result"]
        if isinstance(result, dict) and result.get("status") == "escalated":
            return {
                "status": "escalated",
                "escalation_report": result.get("escalation_report") or {},
                "partial_artifact": result.get("partial_artifact") or {},
                "evaluation_summary": result.get("evaluation_summary") or {},
                "attempts_used": result.get("attempts_used", 1),
                "messages": result.get("messages", []),
                "tool_journal": result.get("tool_journal", []),
                _stage_history_name(stage_id): result.get(_stage_history_name(stage_id), []),
                "events": result.get("events", []),
                "support_files": result.get("support_files", {}),
            }
        return result

    error = final_state.get("error") or {}
    message = error.get("message") or f"{stage_id} stage did not produce a result"
    issues = error.get("issues") or []
    if issues:
        raise RuntimeError(f"{message}: {issues}")
    raise RuntimeError(message)


def _stage_history_name(stage_id: str) -> str:
    if stage_id == "ground":
        return "retry_history"
    return "repair_history"


def _format_context_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, ensure_ascii=False)
    return str(value)
