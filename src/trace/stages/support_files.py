from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Mapping, MutableMapping

from pydantic import BaseModel


class _FilterParams(BaseModel):
    match: str | None = None
    keys: list[str] | None = None
    head_lines: int | None = None


def filtered_view(
    content: str,
    *,
    match: str | None = None,
    keys: list[str] | None = None,
    head_lines: int | None = None,
) -> str:
    if match:
        return _match_window(content, needle=match, context=1)
    if keys:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return content
        if not isinstance(parsed, dict):
            return content
        subset = {key: parsed[key] for key in keys if key in parsed}
        return json.dumps(subset, indent=2, ensure_ascii=False)
    if head_lines is not None and head_lines >= 0:
        return "\n".join(content.splitlines()[:head_lines])
    return content


def _match_window(content: str, *, needle: str, context: int) -> str:
    lines = content.splitlines()
    selected: set[int] = set()
    for idx, line in enumerate(lines):
        if needle in line:
            start = max(0, idx - context)
            stop = min(len(lines), idx + context + 1)
            selected.update(range(start, stop))
    return "\n".join(lines[i] for i in sorted(selected))


def write_support_file(state: MutableMapping[str, Any], relative_path: str, content: str) -> None:
    path = _safe_relative_path(relative_path)
    support_files = dict(state.get("support_files") or {})
    support_files[path] = content
    state["support_files"] = support_files

    root = state.get("support_file_root")
    if root:
        absolute = Path(root) / path
        absolute.parent.mkdir(parents=True, exist_ok=True)
        absolute.write_text(content, encoding="utf-8")


def write_support_json(state: MutableMapping[str, Any], relative_path: str, payload: Any) -> None:
    write_support_file(
        state,
        relative_path,
        json.dumps(payload, indent=2, ensure_ascii=True),
    )


def materialize_support_files(state: MutableMapping[str, Any]) -> None:
    root = state.get("support_file_root")
    if not root:
        return
    for relative_path, content in (state.get("support_files") or {}).items():
        path = _safe_relative_path(str(relative_path))
        absolute = Path(root) / path
        absolute.parent.mkdir(parents=True, exist_ok=True)
        absolute.write_text(str(content), encoding="utf-8")


def support_file_path(state: MutableMapping[str, Any], relative_path: str) -> Path:
    path = _safe_relative_path(relative_path)
    root = state.get("support_file_root")
    if not root:
        return Path(path)
    materialize_support_files(state)
    return Path(root) / path


def merge_support_files(*states: MutableMapping[str, Any]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for state in states:
        for relative_path, content in (state.get("support_files") or {}).items():
            merged[_safe_relative_path(str(relative_path))] = str(content)
    return merged


def load_constraint_entries(
    *,
    support_files: Mapping[str, str],
    constraint_files: Mapping[str, str],
    scope: Literal["logical", "physical"],
    default_path: str,
) -> list[dict[str, Any]]:
    relative_path = str(constraint_files.get(scope) or default_path)
    raw = support_files.get(relative_path, "{}")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []

    entries: list[dict[str, Any]] = []
    for constraint_id, fact in payload.items():
        if not isinstance(fact, dict):
            entries.append({"id": constraint_id})
            continue
        entry: dict[str, Any] = {"id": constraint_id}
        if fact.get("kind") is not None:
            entry["kind"] = fact["kind"]
        if fact.get("statement") is not None:
            entry["statement"] = fact["statement"]
        entries.append(entry)
    return entries


def _safe_relative_path(relative_path: str) -> str:
    raw = str(relative_path or "").replace("\\", "/").strip()
    if not raw:
        raise ValueError("support file path is required")
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe support file path: {relative_path!r}")
    return raw
