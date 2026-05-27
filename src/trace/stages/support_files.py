from __future__ import annotations

import json
from pathlib import Path
from typing import Any, MutableMapping


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


def _safe_relative_path(relative_path: str) -> str:
    raw = str(relative_path or "").replace("\\", "/").strip()
    if not raw:
        raise ValueError("support file path is required")
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe support file path: {relative_path!r}")
    return raw
