from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from trace.runtime.role_client import RoleClient


class CheckpointSpec(BaseModel):
    id: str
    func: str
    description: str
    constraint_ids: list[str]
    args: dict[str, Any]


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
    if "result" in final_state:
        return final_state["result"]

    error = final_state.get("error") or {}
    message = error.get("message") or f"{stage_id} stage did not produce a result"
    issues = error.get("issues") or []
    if issues:
        raise RuntimeError(f"{message}: {issues}")
    raise RuntimeError(message)


def _format_context_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, ensure_ascii=False)
    return str(value)
