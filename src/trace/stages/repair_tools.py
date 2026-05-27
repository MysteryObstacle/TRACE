from __future__ import annotations

from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

from langchain.tools import tool
from pydantic import BaseModel, ConfigDict, Field

from tgraph import TGraph, inspect_graph, validate_graph
from tgraph.operations.mutate import execute_mutation_file
from tgraph.operations.validate import ValidationContext
from trace.stages.support_files import _FilterParams, filtered_view
from trace.tools.images.catalog import find_images, get_image


class MutationSummary(BaseModel):
    stage: str
    node_count: int
    link_count: int
    affected_node_ids: list[str]
    affected_link_ids: list[str]
    op_counts: dict[str, int]

    @classmethod
    def from_operations(
        cls,
        *,
        stage: str,
        node_count: int,
        link_count: int,
        operations: list[dict[str, Any]],
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
        )


def _derive_op_counts(operations: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(op.get("op", "") for op in operations if op.get("op")))


class _InspectGraphToolInput(BaseModel):
    view: str = "summary"
    node_id: str | None = None
    port_id: str | None = None
    source: str | None = None
    target: str | None = None


class _ReadSupportFileInput(_FilterParams):
    path: str


class _WriteSupportFileInput(BaseModel):
    path: str
    content: str


class _WriteMutationFileInput(BaseModel):
    content: str
    path: str | None = None


class _ExecuteMutationFileInput(BaseModel):
    path: str
    run_validate: bool = Field(default=True, alias="validate")
    include_graph: bool = False


class _FindImagesInput(BaseModel):
    query: str | None = None
    roles: list[str] | None = None
    node_type: str | None = None
    limit: int = 10


class _GetImageInput(BaseModel):
    image_id: str


class StageRepairTools:
    def __init__(
        self,
        artifact: dict[str, Any],
        *,
        support_files: dict[str, str] | None = None,
        support_file_root: str | None = None,
        logical_reference_graph: TGraph | dict[str, Any] | None = None,
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
        self._mutation_index = 1

    def artifact_state(self) -> dict[str, Any]:
        return deepcopy(self._artifact)

    def support_files(self) -> dict[str, str]:
        return dict(self._support_files)

    def as_agent_tools(self, *, include_checkpoint_tool: bool = True, include_image_tools: bool = False) -> list[Any]:
        @tool("inspect_graph", args_schema=_InspectGraphToolInput)
        def inspect_graph_tool(
            view: str = "summary",
            node_id: str | None = None,
            port_id: str | None = None,
            source: str | None = None,
            target: str | None = None,
        ) -> dict[str, Any]:
            """Inspect the current graph with summary, node, links, path, or cidrs views."""

            kwargs = {"node_id": node_id, "port_id": port_id, "source": source, "target": target}
            kwargs = {key: value for key, value in kwargs.items() if value is not None}
            return self.inspect_graph(view=view, **kwargs)

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

        @tool("execute_mutation_file", args_schema=_ExecuteMutationFileInput)
        def execute_mutation_file_tool(path: str, run_validate: bool = True, include_graph: bool = False) -> dict[str, Any]:
            """Execute a mutation file transactionally. Returns ok + operations + summary; pass include_graph=true to also receive the full graph."""

            return self.execute_mutation_file(path=path, validate=run_validate, include_graph=include_graph)

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
            validate_graph_tool,
            list_support_files_tool,
        ]
        if include_checkpoint_tool:
            tools.insert(2, write_checkpoint_file_tool)
        if include_image_tools:
            @tool("find_images", args_schema=_FindImagesInput)
            def find_images_tool(
                query: str | None = None,
                roles: list[str] | None = None,
                node_type: str | None = None,
                limit: int = 10,
            ) -> dict[str, Any]:
                """Search the image catalog by free-text query, role list, or node type. Returns ranked candidate images with default_flavor."""

                return {"images": find_images(query=query, roles=roles, node_type=node_type, limit=limit)}

            @tool("get_image", args_schema=_GetImageInput)
            def get_image_tool(image_id: str) -> dict[str, Any]:
                """Look up a specific image_id in the catalog. Returns image, roles, node_types, aliases, default_flavor."""

                try:
                    return get_image(image_id)
                except KeyError as exc:
                    return {"ok": False, "error": {"message": str(exc)}}

            tools.extend([find_images_tool, get_image_tool])
        return tools

    def inspect_graph(self, *, view: str = "summary", **kwargs: Any) -> dict[str, Any]:
        return inspect_graph(self._graph_model(), view=view, **kwargs)

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
            return {"ok": False, "error": {"message": f"support file not found: {normalized}"}}
        content = filtered_view(self._support_files[normalized], match=match, keys=keys, head_lines=head_lines)
        return {"ok": True, "path": normalized, "content": content}

    def list_support_files(self) -> dict[str, Any]:
        return {"paths": sorted(self._support_files.keys())}

    def write_checkpoint_file(self, *, path: str, content: str) -> dict[str, Any]:
        normalized = _safe_relative_path(path)
        stage = self._graph_model().stage
        expected = f"{stage}/checkpoints.py"
        if normalized != expected:
            return {"ok": False, "error": {"message": f"{stage} checkpoint file must be {expected}"}}
        self._write_support_file(normalized, content)
        self._artifact.setdefault("checkpoint_files", {})[stage] = normalized
        return {"ok": True, "path": normalized, "checkpoint_files": deepcopy(self._artifact.get("checkpoint_files", {}))}

    def write_mutation_file(self, *, content: str, path: str | None = None) -> dict[str, Any]:
        normalized = _safe_relative_path(path or self._next_mutation_path())
        self._write_support_file(normalized, content)
        return {"ok": True, "path": normalized}

    def execute_mutation_file(self, *, path: str, validate: bool = True, include_graph: bool = False) -> dict[str, Any]:
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
        graph_model = self._graph_model()
        summary = MutationSummary.from_operations(
            stage=graph_model.stage,
            node_count=len(graph_model.nodes),
            link_count=len(graph_model.links),
            operations=operations,
        )
        payload: dict[str, Any] = {
            "ok": result.ok,
            "operations": [dict(op) for op in operations],
            "summary": summary.model_dump(mode="json"),
        }
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


def _safe_relative_path(relative_path: str) -> str:
    raw = str(relative_path or "").replace("\\", "/").strip()
    path = Path(raw)
    if not raw or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe support file path: {relative_path!r}")
    return raw
