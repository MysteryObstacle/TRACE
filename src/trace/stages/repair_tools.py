from __future__ import annotations

import json
import re
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

from langchain.tools import tool
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from tgraph import TGraph, inspect_graph as _inspect_graph_view, validate_graph
from tgraph.operations.mutate import execute_mutation_file
from tgraph.operations.validate import ValidationContext
from trace.stages.support_files import _FilterParams, filtered_view
from trace.tools.images.agent_surface import build_image_agent_tools


class MutationSummary(BaseModel):
    stage: str
    node_count: int
    link_count: int
    affected_node_ids: list[str]
    affected_link_ids: list[str]
    op_counts: dict[str, int]
    snapshot_path: str | None = None

    @classmethod
    def from_operations(
        cls,
        *,
        stage: str,
        node_count: int,
        link_count: int,
        operations: list[dict[str, Any]],
        snapshot_path: str | None = None,
    ) -> MutationSummary:
        node_ids: set[str] = set()
        link_ids: set[str] = set()
        for op in operations:
            if isinstance(op.get("node"), str):
                node_ids.add(op["node"])
            if isinstance(op.get("nodes"), list):
                node_ids.update(item for item in op["nodes"] if isinstance(item, str))
            if isinstance(op.get("segment"), str):
                node_ids.add(op["segment"])
            if isinstance(op.get("link"), str):
                link_ids.add(op["link"])
            if isinstance(op.get("links_removed"), list):
                link_ids.update(item for item in op["links_removed"] if isinstance(item, str))
            if isinstance(op.get("ports_removed"), list):
                for token in op["ports_removed"]:
                    if not isinstance(token, str):
                        continue
                    node_part = token.split(".", 1)[0]
                    if node_part:
                        node_ids.add(node_part)
        return cls(
            stage=stage,
            node_count=node_count,
            link_count=link_count,
            affected_node_ids=sorted(node_ids),
            affected_link_ids=sorted(link_ids),
            op_counts=_derive_op_counts(operations),
            snapshot_path=snapshot_path,
        )


def _derive_op_counts(operations: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(op.get("op", "") for op in operations if op.get("op")))


_CHECK_FN_PATTERN = re.compile(r"^\s*def\s+(check_[A-Za-z0-9_]+)\s*\(", re.MULTILINE)


def _derive_produced_files(attempted_actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest_exec_by_path: dict[str, dict[str, Any]] = {}
    for action in attempted_actions:
        if action.get("tool") != "execute_mutation_file":
            continue
        path = (action.get("args") or {}).get("path")
        if not isinstance(path, str):
            continue
        if action.get("ok") is True:
            latest_exec_by_path[path] = action

    produced: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    for action in attempted_actions:
        tool_name = action.get("tool")
        args = action.get("args") or {}

        if tool_name == "write_mutation_file":
            path = args.get("path")
            if not isinstance(path, str) or path in seen_paths:
                continue
            seen_paths.add(path)
            paired_execute = latest_exec_by_path.get(path)
            summary_dict = ((paired_execute or {}).get("result") or {}).get("summary") or {}
            op_counts = summary_dict.get("op_counts") or {}
            node_targets = list(summary_dict.get("affected_node_ids") or [])
            snapshot_path = summary_dict.get("snapshot_path")
            produced.append(
                {
                    "path": path,
                    "file_kind": "mutation",
                    "node_targets": node_targets,
                    "op_counts": op_counts,
                    "summary_one_line": _summary_one_line_for_mutation(op_counts, node_targets),
                    "snapshot_path": snapshot_path,
                }
            )

        elif tool_name == "write_checkpoint_file":
            path = args.get("path")
            if not isinstance(path, str) or path in seen_paths:
                continue
            seen_paths.add(path)
            content = args.get("content") or ""
            fn_names = _CHECK_FN_PATTERN.findall(content)
            produced.append(
                {
                    "path": path,
                    "file_kind": "checkpoint",
                    "node_targets": [],
                    "op_counts": {},
                    "summary_one_line": _summary_one_line_for_checkpoint(fn_names),
                    "snapshot_path": None,
                }
            )

    return produced


def _summary_one_line_for_mutation(op_counts: dict[str, int], node_targets: list[str]) -> str:
    if not op_counts:
        return "mutation written; not yet executed"
    op_part = ", ".join(f"{op} x{count}" for op, count in sorted(op_counts.items()))
    if not node_targets:
        return op_part
    display = node_targets[:5]
    tail = f", ... +{len(node_targets) - 5} more" if len(node_targets) > 5 else ""
    return f"{op_part} on [{', '.join(display)}{tail}]"


def _summary_one_line_for_checkpoint(fn_names: list[str]) -> str:
    if not fn_names:
        return "checkpoint defines: <unknown>"
    display = fn_names[:5]
    tail = f", ... +{len(fn_names) - 5} more" if len(fn_names) > 5 else ""
    return f"checkpoint defines: {', '.join(display)}{tail}"


class _InspectGraphToolInput(BaseModel):
    view: str = "summary"
    node_id: str | None = None
    port_id: str | None = None
    source: str | None = None
    target: str | None = None
    against: str | None = None
    baseline_attempt_id: int | None = None


class _ReadSupportFileInput(_FilterParams):
    path: str


class _WriteSupportFileInput(BaseModel):
    path: str
    content: str


class _WriteMutationFileInput(BaseModel):
    content: str
    path: str | None = None


class _ExecuteMutationFileInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    path: str
    run_validate: bool = Field(default=False, alias="validate")
    include_graph: bool = False
    include_operations: bool = False

    @classmethod
    def model_json_schema(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
        kwargs["by_alias"] = True
        return super().model_json_schema(*args, **kwargs)

    @classmethod
    def schema(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
        kwargs["by_alias"] = True
        return super().schema(*args, **kwargs)


class _AliasArgsStructuredTool(StructuredTool):
    @property
    def args(self) -> dict:
        if self.args_schema is not None:
            return self.args_schema.model_json_schema(by_alias=True)["properties"]
        return super().args


class StageRepairTools:
    def __init__(
        self,
        artifact: dict[str, Any],
        *,
        support_files: dict[str, str] | None = None,
        support_file_root: str | None = None,
        logical_reference_graph: TGraph | dict[str, Any] | None = None,
        mutation_index_seed: int = 1,
    ) -> None:
        self._artifact = deepcopy(artifact)
        self._support_files = dict(support_files or {})
        self._support_file_root = support_file_root
        self._logical_reference_graph = (
            logical_reference_graph
            if isinstance(logical_reference_graph, TGraph)
            else TGraph.model_validate(logical_reference_graph)
            if logical_reference_graph is not None
            else None
        )
        self._mutation_index = max(1, mutation_index_seed, self._next_existing_mutation_index())
        self._state_change_closed_reason: str | None = None

    def artifact_state(self) -> dict[str, Any]:
        return deepcopy(self._artifact)

    def support_files(self) -> dict[str, str]:
        return dict(self._support_files)

    def as_agent_tools(
        self,
        *,
        include_checkpoint_tool: bool = True,
        include_image_tools: bool = False,
        include_validate_tool: bool = False,
    ) -> list[Any]:
        @tool("inspect_graph", args_schema=_InspectGraphToolInput)
        def inspect_graph_tool(
            view: str = "summary",
            node_id: str | None = None,
            port_id: str | None = None,
            source: str | None = None,
            target: str | None = None,
            against: str | None = None,
            baseline_attempt_id: int | None = None,
        ) -> dict[str, Any]:
            """Inspect the current graph. Views: summary, nodes, node, links, path, cidrs, diff. For view='diff' pass against='previous_attempt' or 'logical_reference'."""

            kwargs = {"node_id": node_id, "port_id": port_id, "source": source, "target": target}
            kwargs = {key: value for key, value in kwargs.items() if value is not None}
            return self.inspect_graph(
                view=view,
                against=against,
                baseline_attempt_id=baseline_attempt_id,
                **kwargs,
            )

        @tool("read_support_file", args_schema=_ReadSupportFileInput)
        def read_support_file_tool(
            path: str,
            match: str | None = None,
            keys: list[str] | None = None,
            head_lines: int | None = None,
        ) -> dict[str, Any]:
            """Read a support file with optional substring match, JSON key filter, or head-lines window."""

            return self.read_support_file(path, match=match, keys=keys, head_lines=head_lines)

        @tool("write_checkpoint_file", args_schema=_WriteSupportFileInput)
        def write_checkpoint_file_tool(path: str, content: str) -> dict[str, Any]:
            """Create or replace a checkpoint Python file such as logical/checkpoints.py or physical/checkpoints.py."""

            return self.write_checkpoint_file(path=path, content=content)

        @tool("write_mutation_file", args_schema=_WriteMutationFileInput)
        def write_mutation_file_tool(content: str, path: str | None = None) -> dict[str, Any]:
            """Write a mutation file defining mutate(tgraph)."""

            return self.write_mutation_file(content=content, path=path)

        def _execute_mutation_file_tool(
            path: str,
            run_validate: bool = False,
            include_graph: bool = False,
            include_operations: bool = False,
        ) -> dict[str, Any]:
            """Execute a mutation file transactionally. By default this applies only; the validator node runs full validation."""

            return self.execute_mutation_file(
                path=path,
                validate=run_validate,
                include_graph=include_graph,
                include_operations=include_operations,
            )

        execute_mutation_file_tool = _AliasArgsStructuredTool.from_function(
            func=_execute_mutation_file_tool,
            name="execute_mutation_file",
            description="Execute a mutation file transactionally. By default this applies only; the validator node runs full validation.",
            args_schema=_ExecuteMutationFileInput,
        )

        @tool("validate_graph")
        def validate_graph_tool() -> dict[str, Any]:
            """Validate the current artifact graph using file-backed constraints and checkpoints."""

            return self.validate_graph()

        @tool("list_support_files")
        def list_support_files_tool() -> dict[str, Any]:
            """List all support file paths currently accessible to the agent."""

            return self.list_support_files()

        tools = [
            inspect_graph_tool,
            read_support_file_tool,
            write_mutation_file_tool,
            execute_mutation_file_tool,
            list_support_files_tool,
        ]
        if include_validate_tool:
            tools.insert(4, validate_graph_tool)
        if include_checkpoint_tool:
            tools.insert(2, write_checkpoint_file_tool)
        if include_image_tools:
            tools.extend(build_image_agent_tools())
        return tools

    def inspect_graph(
        self,
        *,
        view: str = "summary",
        against: str | None = None,
        baseline_attempt_id: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        param_error = _inspect_view_param_error(view=view, kwargs=kwargs)
        if param_error is not None:
            return param_error
        if view == "nodes":
            return _nodes_view(self._graph_model())
        if view == "diff":
            baseline_graph = self._resolve_diff_baseline(against=against, baseline_attempt_id=baseline_attempt_id)
            if isinstance(baseline_graph, dict) and baseline_graph.get("ok") is False:
                return baseline_graph
            return _inspect_graph_view(self._graph_model(), view="diff", baseline=baseline_graph)
        if view not in _ALLOWED_INSPECT_VIEWS:
            return _unknown_inspect_view(view)
        try:
            return _inspect_graph_view(self._graph_model(), view=view, **kwargs)
        except ValueError as exc:
            return {"ok": False, "error": {"message": str(exc)}, "allowed_views": sorted(_ALLOWED_INSPECT_VIEWS)}

    def read_support_file(
        self,
        path: str,
        *,
        match: str | None = None,
        keys: list[str] | None = None,
        head_lines: int | None = None,
    ) -> dict[str, Any]:
        normalized = _safe_relative_path(path)
        if normalized not in self._support_files:
            catalog = _read_catalog_file(normalized)
            if catalog is not None:
                doc_path, doc_content = catalog
                content = filtered_view(doc_content, match=match, keys=keys, head_lines=head_lines)
                return {"ok": True, "path": doc_path, "content": content}
            doc = _read_agent_doc(normalized)
            if doc is None:
                return {"ok": False, "error": {"message": f"support file not found: {normalized}"}}
            doc_path, doc_content = doc
            content = filtered_view(doc_content, match=match, keys=keys, head_lines=head_lines)
            return {"ok": True, "path": doc_path, "content": content}
        content = filtered_view(self._support_files[normalized], match=match, keys=keys, head_lines=head_lines)
        return {"ok": True, "path": normalized, "content": content}

    def list_support_files(self) -> dict[str, Any]:
        support_paths = sorted(self._support_files.keys())
        agent_docs = _agent_doc_paths()
        return {"paths": support_paths, "support_files": support_paths, "agent_docs": agent_docs}

    def write_checkpoint_file(self, *, path: str, content: str) -> dict[str, Any]:
        closed = self._closed_response()
        if closed is not None:
            return closed
        normalized = _safe_relative_path(path)
        stage = self._graph_model().stage
        expected = f"{stage}/checkpoints.py"
        if normalized != expected:
            return {"ok": False, "error": {"message": f"{stage} checkpoint file must be {expected}"}}
        self._write_support_file(normalized, content)
        self._artifact.setdefault("checkpoint_files", {})[stage] = normalized
        self._state_change_closed_reason = f"checkpoint file written at {normalized}; return control to the validator"
        return {
            "ok": True,
            "path": normalized,
            "checkpoint_files": deepcopy(self._artifact.get("checkpoint_files", {})),
            "stop": True,
            "next": "return control to validator",
        }

    def write_mutation_file(self, *, content: str, path: str | None = None) -> dict[str, Any]:
        closed = self._closed_response()
        if closed is not None:
            return closed
        normalized = _safe_relative_path(path or self._next_mutation_path())
        self._write_support_file(normalized, content)
        return {"ok": True, "path": normalized}

    def execute_mutation_file(
        self,
        *,
        path: str,
        validate: bool = False,
        include_graph: bool = False,
        include_operations: bool = False,
    ) -> dict[str, Any]:
        closed = self._closed_response()
        if closed is not None:
            return closed
        normalized = _safe_relative_path(path)
        if normalized not in self._support_files:
            return {"ok": False, "error": {"message": f"support file not found: {normalized}"}}
        mutation_path = self._materialize_support_file(normalized)
        result = execute_mutation_file(
            self._graph_model(),
            mutation_path=mutation_path,
            validate=validate,
            validation_context=self._validation_context(),
        )
        operations = list(result.operations or [])
        if result.ok and result.graph is not None:
            self._artifact["graph"] = result.graph.model_dump(mode="json")
            self._state_change_closed_reason = f"mutation applied from {normalized}; return control to the validator"

        snapshot_path: str | None = None
        if result.ok and result.graph is not None:
            attempt_id = self._attempt_id_for_mutation_path(normalized)
            if attempt_id is not None:
                snapshot_path = f"{result.graph.stage}/mutations/snapshots/attempt_{attempt_id}.json"
                self._write_support_file(
                    snapshot_path,
                    json.dumps(result.graph.model_dump(mode="json"), indent=2, ensure_ascii=False),
                )

        graph_model = self._graph_model()
        summary = MutationSummary.from_operations(
            stage=graph_model.stage,
            node_count=len(graph_model.nodes),
            link_count=len(graph_model.links),
            operations=operations,
            snapshot_path=snapshot_path,
        )
        payload: dict[str, Any] = {
            "ok": result.ok,
            "summary": summary.model_dump(mode="json"),
        }
        if result.ok:
            payload["stop"] = True
            payload["next"] = "return control to validator"
        if include_operations:
            payload["operations"] = [dict(op) for op in operations]
        if not result.ok:
            payload["issues"] = [issue.model_dump(mode="json") for issue in result.issues]
        if include_graph and result.graph is not None:
            payload["graph"] = result.graph.model_dump(mode="json")
        return payload

    def validate_graph(self) -> dict[str, Any]:
        self._materialize_all_support_files()
        return validate_graph(self._graph_model(), context=self._validation_context()).model_dump(mode="json")

    def _graph_model(self) -> TGraph:
        return TGraph.model_validate(self._artifact["graph"])

    def _validation_context(self) -> ValidationContext:
        graph = self._graph_model()
        constraint_files = {
            scope: str(self._materialize_support_file(path))
            for scope, path in (self._artifact.get("constraint_files") or {}).items()
            if path in self._support_files
        }
        checkpoint_files = {
            scope: str(self._materialize_support_file(path))
            for scope, path in (self._artifact.get("checkpoint_files") or {}).items()
            if path in self._support_files
        }
        if graph.stage == "physical":
            references = {"logical": self._logical_reference_graph} if self._logical_reference_graph is not None else {}
            return ValidationContext(
                preserve_topology_from=self._logical_reference_graph,
                required_node_fields=[],
                constraint_files=constraint_files,
                checkpoint_files=checkpoint_files,
                references=references,
            )
        return ValidationContext(
            constraint_files=constraint_files,
            checkpoint_files=checkpoint_files,
        )

    def _write_support_file(self, path: str, content: str) -> None:
        normalized = _safe_relative_path(path)
        self._support_files[normalized] = content
        if self._support_file_root:
            absolute = Path(self._support_file_root) / normalized
            absolute.parent.mkdir(parents=True, exist_ok=True)
            absolute.write_text(content, encoding="utf-8")

    def _materialize_all_support_files(self) -> None:
        for path in list(self._support_files):
            self._materialize_support_file(path)

    def _materialize_support_file(self, path: str) -> Path:
        normalized = _safe_relative_path(path)
        if not self._support_file_root:
            return Path(normalized)
        absolute = Path(self._support_file_root) / normalized
        absolute.parent.mkdir(parents=True, exist_ok=True)
        absolute.write_text(self._support_files[normalized], encoding="utf-8")
        return absolute

    def _next_mutation_path(self) -> str:
        stage = self._graph_model().stage
        path = f"{stage}/mutations/attempt_{self._mutation_index}.py"
        self._mutation_index += 1
        return path

    def _next_existing_mutation_index(self) -> int:
        stage = self._graph_model().stage
        highest = 0
        patterns = (
            re.compile(rf"^{re.escape(stage)}/mutations/attempt_(\d+)\.py$"),
            re.compile(rf"^{re.escape(stage)}/mutations/snapshots/attempt_(\d+)\.json$"),
        )
        for path in self._support_files:
            for pattern in patterns:
                match = pattern.match(path)
                if match:
                    highest = max(highest, int(match.group(1)))
        return highest + 1 if highest else 1

    def _attempt_id_for_mutation_path(self, path: str) -> int | None:
        match = re.match(r"^[^/]+/mutations/attempt_(\d+)\.py$", path)
        if not match:
            return None
        return int(match.group(1))

    def _resolve_diff_baseline(
        self,
        *,
        against: str | None,
        baseline_attempt_id: int | None,
    ) -> Any:
        if against == "logical_reference":
            if self._logical_reference_graph is None:
                return {"ok": False, "error": {"message": "logical_reference graph not provided"}}
            return self._logical_reference_graph
        if against in ("previous_attempt", None):
            stage = self._graph_model().stage
            snapshot_prefix = f"{stage}/mutations/snapshots/attempt_"
            if baseline_attempt_id is not None:
                path = f"{snapshot_prefix}{baseline_attempt_id}.json"
                if path not in self._support_files:
                    return {"ok": False, "error": {"message": f"snapshot not found: {path}"}}
                return TGraph.model_validate(json.loads(self._support_files[path]))
            candidates = sorted(
                (key for key in self._support_files if key.startswith(snapshot_prefix) and key.endswith(".json")),
                key=lambda key: int(key.rsplit("_", 1)[-1].split(".")[0]),
            )
            if not candidates:
                return {"ok": False, "error": {"message": "no previous attempt snapshot available"}}
            return TGraph.model_validate(json.loads(self._support_files[candidates[-1]]))
        return {"ok": False, "error": {"message": f"unknown against: {against!r}"}}

    def _closed_response(self) -> dict[str, Any] | None:
        if self._state_change_closed_reason is None:
            return None
        return {
            "ok": False,
            "stop": True,
            "error": {
                "message": self._state_change_closed_reason,
            },
            "next": "return control to validator",
        }


def _safe_relative_path(relative_path: str) -> str:
    raw = str(relative_path or "").replace("\\", "/").strip()
    path = Path(raw)
    if not raw or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe support file path: {relative_path!r}")
    return raw


_ALLOWED_INSPECT_VIEWS = {"summary", "nodes", "node", "links", "path", "cidrs", "diff"}


def _inspect_view_param_error(*, view: str, kwargs: dict[str, Any]) -> dict[str, Any] | None:
    if view == "node" and not kwargs.get("node_id"):
        return {"ok": False, "error": {"message": "inspect_graph view='node' requires node_id"}}
    if view == "path":
        if not kwargs.get("source") or not kwargs.get("target"):
            return {"ok": False, "error": {"message": "inspect_graph view='path' requires source and target"}}
    return None


def _unknown_inspect_view(view: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {"message": f"unknown inspect view: {view}"},
        "allowed_views": sorted(_ALLOWED_INSPECT_VIEWS),
    }


def _nodes_view(graph: TGraph) -> dict[str, Any]:
    nodes = [
        {
            "id": node.id,
            "type": node.type,
            "label": node.label,
            "port_count": len(node.ports),
            **({"image": node.image} if node.image is not None else {}),
            **({"flavor": node.flavor} if node.flavor is not None else {}),
        }
        for node in graph.nodes
    ]
    return {"ok": True, "stage": graph.stage, "nodes": nodes}


def _agent_docs_root() -> Path:
    return Path(__file__).resolve().parents[2] / "tgraph" / "agent" / "docs"


def _agent_doc_paths() -> list[str]:
    root = _agent_docs_root()
    if not root.exists():
        return []
    return [f"docs/{path.name}" for path in sorted(root.glob("*.md"))]


def _read_catalog_file(path: str) -> tuple[str, str] | None:
    normalized = _safe_relative_path(path)
    aliases = {
        "catalog/image_catalog.v1.json",
        "data/trace/image_catalog.v1.json",
        "image_catalog.v1.json",
    }
    if normalized not in aliases:
        return None
    try:
        from trace.tools.images.loader import catalog_json_path

        catalog_path = catalog_json_path()
    except ImportError:
        return None
    if not catalog_path.is_file():
        return None
    return "catalog/image_catalog.v1.json", catalog_path.read_text(encoding="utf-8")


def _read_agent_doc(path: str) -> tuple[str, str] | None:
    normalized = _safe_relative_path(path)
    doc_name = normalized.removeprefix("docs/")
    if "/" in doc_name or not doc_name.endswith(".md"):
        return None
    doc_path = _agent_docs_root() / doc_name
    if not doc_path.exists() or not doc_path.is_file():
        return None
    return f"docs/{doc_name}", doc_path.read_text(encoding="utf-8")
