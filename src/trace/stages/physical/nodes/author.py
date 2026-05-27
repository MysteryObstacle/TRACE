from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from langchain.tools import tool
from pydantic import BaseModel

from trace.stages.common import build_messages
from trace.stages.physical.state import PhysicalState
from trace.stages.prompt_contracts import load_tgraph_contract_for
from trace.stages.ground.schemas import PHYSICAL_CONSTRAINTS_PATH
from trace.stages.support_files import write_support_file
from trace.tools.images.catalog import image_catalog_prompt


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "author.md"
DEFAULT_CHECKPOINT_PATH = "physical/checkpoints.py"
DEFAULT_CONSTRAINT_PATH = PHYSICAL_CONSTRAINTS_PATH
MAX_TOOL_CALLS = 24


def author_node(state: PhysicalState, role_client) -> PhysicalState:
    ground_artifact = state.get("ground_artifact", {})
    author_tools = PhysicalAuthorTools(
        state=state,
        physical_constraints=_physical_constraint_ids(state),
    )
    messages = build_messages(
        system_prompt=PROMPT_PATH.read_text(encoding="utf-8").strip(),
        task="Author physical-stage checkpoint functions for the current logical graph.",
        context_sections={
            "constraint_files": state.get("draft_artifact", {}).get("constraint_files", {})
            or ground_artifact.get("constraint_files", {"physical": DEFAULT_CONSTRAINT_PATH}),
        },
        system_context_sections={
            "tgraph_contract": load_tgraph_contract_for("physical_author"),
            "image_catalog": image_catalog_prompt(),
        },
    )
    agent_result = role_client.invoke_agent(
        role_name="physical_author",
        messages=messages,
        tools=author_tools.as_agent_tools(),
        max_tool_calls=MAX_TOOL_CALLS,
    )
    validation = author_tools.validate_checkpoint_file()
    if not validation["ok"]:
        raise ValueError(f"physical author produced invalid checkpoint file: {validation['issues']}")

    state["author_output"] = author_tools.artifact_state()
    state["messages"] = _extract_messages(agent_result) or messages
    state["events"] = [*state.get("events", []), {"type": "physical.author.completed"}]
    return state


class _WriteCheckpointFileInput(BaseModel):
    content: str
    path: str = DEFAULT_CHECKPOINT_PATH


class _RemoveCheckpointFileInput(BaseModel):
    path: str = DEFAULT_CHECKPOINT_PATH


class PhysicalAuthorTools:
    def __init__(self, *, state: PhysicalState, physical_constraints: list[dict[str, Any]]) -> None:
        self._state = state
        self._known_constraint_ids = {
            str(item.get("id") or "").strip()
            for item in physical_constraints
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        }
        self._checkpoint_files: dict[str, str] = {}

    def artifact_state(self) -> dict[str, Any]:
        return {"checkpoint_files": dict(sorted(self._checkpoint_files.items()))}

    def as_agent_tools(self) -> list[Any]:
        @tool("write_checkpoint_file", args_schema=_WriteCheckpointFileInput)
        def write_checkpoint_file_tool(content: str, path: str = DEFAULT_CHECKPOINT_PATH) -> dict[str, Any]:
            """Create or replace a Python checkpoint file containing check_<constraint_id>(tgraph) functions."""

            return self.write_checkpoint_file(content=content, path=path)

        @tool("remove_checkpoint_file", args_schema=_RemoveCheckpointFileInput)
        def remove_checkpoint_file_tool(path: str = DEFAULT_CHECKPOINT_PATH) -> dict[str, Any]:
            """Remove an authored checkpoint file reference and its in-memory support content."""

            return self.remove_checkpoint_file(path)

        @tool("read_constraint_file")
        def read_constraint_file_tool(path: str = DEFAULT_CONSTRAINT_PATH) -> dict[str, Any]:
            """Read a generated constraint fact file from the current support files."""

            content = (self._state.get("support_files") or {}).get(path)
            if content is None:
                return {"ok": False, "error": {"message": f"support file not found: {path}"}}
            return {"ok": True, "path": path, "content": content}

        @tool("validate_checkpoint_file")
        def validate_checkpoint_file_tool(path: str = DEFAULT_CHECKPOINT_PATH) -> dict[str, Any]:
            """Validate checkpoint file syntax and check_<constraint_id> coverage."""

            return self.validate_checkpoint_file(path)

        return [
            write_checkpoint_file_tool,
            remove_checkpoint_file_tool,
            read_constraint_file_tool,
            validate_checkpoint_file_tool,
        ]

    def write_checkpoint_file(self, *, content: str, path: str = DEFAULT_CHECKPOINT_PATH) -> dict[str, Any]:
        normalized_path = _normalize_checkpoint_path(path)
        issues = _checkpoint_file_static_issues(
            content,
            known_constraint_ids=self._known_constraint_ids,
            source_path=normalized_path,
        )
        if issues:
            return {"ok": False, "issues": issues}
        write_support_file(self._state, normalized_path, content)
        self._checkpoint_files["physical"] = normalized_path
        return {"ok": True, "checkpoint_files": dict(self._checkpoint_files)}

    def remove_checkpoint_file(self, path: str = DEFAULT_CHECKPOINT_PATH) -> dict[str, Any]:
        normalized_path = _normalize_checkpoint_path(path)
        support_files = dict(self._state.get("support_files") or {})
        support_files.pop(normalized_path, None)
        self._state["support_files"] = support_files
        for scope, existing in list(self._checkpoint_files.items()):
            if existing == normalized_path:
                del self._checkpoint_files[scope]
        return {"ok": True, "checkpoint_files": dict(self._checkpoint_files)}

    def validate_checkpoint_file(self, path: str = DEFAULT_CHECKPOINT_PATH) -> dict[str, Any]:
        if not self._known_constraint_ids and not self._checkpoint_files:
            return {"ok": True, "issues": [], "checkpoint_files": {}}
        normalized_path = _normalize_checkpoint_path(path)
        source = (self._state.get("support_files") or {}).get(normalized_path)
        if source is None:
            return {
                "ok": False,
                "issues": [
                    {
                        "issue_kind": "checkpoint.coverage.missing_file",
                        "message": f"missing checkpoint file: {normalized_path}",
                        "checkpoint_path": normalized_path,
                    }
                ],
            }
        issues = _checkpoint_file_static_issues(
            source,
            known_constraint_ids=self._known_constraint_ids,
            source_path=normalized_path,
        )
        return {"ok": not issues, "issues": issues, "checkpoint_files": dict(self._checkpoint_files)}


def _checkpoint_file_static_issues(
    source: str,
    *,
    known_constraint_ids: set[str],
    source_path: str,
) -> list[dict[str, Any]]:
    if not str(source or "").strip():
        return [
            {
                "issue_kind": "checkpoint.file.empty",
                "message": "checkpoint file content is required",
                "checkpoint_path": source_path,
            }
        ]
    try:
        module = ast.parse(source, filename=source_path)
    except SyntaxError as exc:
        return [
            {
                "issue_kind": "checkpoint.file.syntax_error",
                "message": f"checkpoint file syntax error: {exc}",
                "checkpoint_path": source_path,
                "line": exc.lineno,
                "offset": exc.offset,
            }
        ]

    names = [
        node.name
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("check_")
    ]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    issues: list[dict[str, Any]] = []
    for duplicate in duplicates:
        issues.append(
            {
                "issue_kind": "checkpoint.file.duplicate_function",
                "message": f"duplicate checkpoint function: {duplicate}",
                "checkpoint_path": source_path,
                "checkpoint_function": duplicate,
            }
        )

    available = set(names)
    expected = {f"check_{constraint_id}" for constraint_id in known_constraint_ids}
    for missing in sorted(expected - available):
        constraint_id = missing.removeprefix("check_")
        issues.append(
            {
                "issue_kind": "checkpoint.coverage.missing_function",
                "message": f"missing checkpoint function: {missing}",
                "checkpoint_path": source_path,
                "checkpoint_function": missing,
                "constraint_id": constraint_id,
            }
        )
    for orphan in sorted(available - expected):
        issues.append(
            {
                "issue_kind": "checkpoint.coverage.orphan_function",
                "message": f"checkpoint function has no matching constraint: {orphan}",
                "checkpoint_path": source_path,
                "checkpoint_function": orphan,
            }
        )
    return issues


def _normalize_checkpoint_path(path: str) -> str:
    normalized = str(path or DEFAULT_CHECKPOINT_PATH).replace("\\", "/").strip()
    if normalized != DEFAULT_CHECKPOINT_PATH:
        raise ValueError(f"physical author checkpoint path must be {DEFAULT_CHECKPOINT_PATH!r}")
    return normalized


def _physical_constraint_ids(state: PhysicalState) -> list[dict[str, Any]]:
    path = (
        state.get("draft_artifact", {}).get("constraint_files", {}).get("physical")
        or state.get("ground_artifact", {}).get("constraint_files", {}).get("physical")
        or DEFAULT_CONSTRAINT_PATH
    )
    import json

    raw = (state.get("support_files") or {}).get(path, "{}")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    return [{"id": constraint_id} for constraint_id in payload]


def _extract_messages(agent_result: Any) -> list[dict[str, Any]]:
    if isinstance(agent_result, dict):
        messages = agent_result.get("messages")
        if isinstance(messages, list):
            return [item for item in messages if isinstance(item, dict) and item.get("role")]
    return []
