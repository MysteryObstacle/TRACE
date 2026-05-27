from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any


class BackendResolutionError(Exception):
    pass


def add_trace_backend_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--trace-root", default=None, help="Path to the TRACE repository root.")
    parser.add_argument("--trace-python", default=None, help="Python executable with TRACE installed.")


def resolve_trace_backend(trace_root: str | None = None, trace_python: str | None = None) -> dict[str, Any]:
    selected_python = trace_python or os.environ.get("TGRAPH_TRACE_PYTHON")
    if selected_python:
        return {"mode": "python", "python": selected_python}

    selected_root = trace_root or os.environ.get("TGRAPH_TRACE_ROOT")
    root_path: Path | None = None
    if selected_root:
        root_path = Path(selected_root).resolve()
        src_path = root_path / "src"
        if not src_path.exists():
            raise BackendResolutionError(f"TRACE src directory not found: {src_path}")
        sys.path.insert(0, str(src_path))

    module = importlib.import_module("tgraph")
    module_file = Path(getattr(module, "__file__", "")).resolve()
    if root_path is not None and root_path not in module_file.parents:
        raise BackendResolutionError(f"loaded tgraph module outside TRACE root: {module_file}")
    return {"mode": "inprocess", "module": module}


def infer_artifact_stage(artifact: dict[str, Any]) -> str:
    graph = artifact.get("graph")
    if not isinstance(graph, dict):
        raise ValueError("artifact is missing graph object")
    stage = str(graph.get("stage") or "").strip()
    if stage not in {"logical", "physical"}:
        raise ValueError(f"artifact graph.stage must be logical or physical, got: {stage!r}")
    return stage


def load_stage_artifact(artifact: dict[str, Any], *, stage: str | None = None) -> tuple[str, dict[str, Any]]:
    resolved_stage = stage or infer_artifact_stage(artifact)
    model = _artifact_model(resolved_stage).model_validate(artifact)
    return resolved_stage, model.model_dump(mode="json")


def validate_stage_artifact(
    artifact: dict[str, Any],
    *,
    stage: str | None = None,
    levels: list[str] | None = None,
    logical_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from tgraph import TGraph, validate_graph
    from tgraph.operations.validate import ValidationPolicy

    resolved_stage, normalized = load_stage_artifact(artifact, stage=stage)
    policy = ValidationPolicy(levels=levels or ["f1", "f2", "f3", "f4"])
    context = _validation_context(resolved_stage, normalized, logical_artifact=logical_artifact)
    report = validate_graph(TGraph.model_validate(normalized["graph"]), policy=policy, context=context)
    return report.model_dump(mode="json")


def inspect_stage_artifact(
    artifact: dict[str, Any],
    *,
    stage: str | None = None,
    query: str,
    query_id: str | None = None,
    node: str | None = None,
    source: str | None = None,
    target: str | None = None,
    text: str | None = None,
) -> Any:
    from tgraph import inspect_graph

    _, normalized = load_stage_artifact(artifact, stage=stage)
    graph = normalized["graph"]

    if query in {"summary", "topology"}:
        return inspect_graph(graph, view="summary")
    if query == "node":
        if not query_id:
            raise ValueError("--id is required for node query")
        return inspect_graph(graph, view="node", node_id=query_id)
    if query == "links":
        kwargs: dict[str, Any] = {}
        if node is not None:
            kwargs["node_id"] = node
        if query_id is not None:
            kwargs["port_id"] = query_id
        return inspect_graph(graph, view="links", **kwargs)
    if query == "path":
        if not source or not target:
            raise ValueError("--source and --target are required for path query")
        return inspect_graph(graph, view="path", source=source, target=target)
    if query == "cidrs":
        return inspect_graph(graph, view="cidrs")
    if query == "support-files":
        return _filter_support_files(normalized, text or "")
    raise ValueError(f"unknown query: {query}")


def export_stage_artifact(artifact: dict[str, Any], *, stage: str | None = None, target: str) -> dict[str, Any]:
    from tgraph import emit_target

    resolved_stage, normalized = load_stage_artifact(artifact, stage=stage)
    if target == "tgraph-json":
        return {
            "ok": True,
            "target": target,
            "files": [{"path": "tgraph.json", "content": json_dumps(normalized["graph"])}],
        }
    result = emit_target(target, normalized["graph"]).model_dump(mode="json")
    if result.get("ok") and resolved_stage:
        return result
    return result


def json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def print_json(payload: Any, exit_code: int = 0) -> None:
    print(json_dumps(payload))
    raise SystemExit(exit_code)


def _artifact_model(stage: str):
    from trace.stages.artifacts import LogicalArtifact, PhysicalArtifact

    return LogicalArtifact if stage == "logical" else PhysicalArtifact


def _validation_context(stage: str, artifact: dict[str, Any], *, logical_artifact: dict[str, Any] | None = None):
    from tgraph import TGraph
    from tgraph.operations.validate import ValidationContext

    constraint_files = _file_refs(artifact.get("constraint_files", {}))
    checkpoint_files = _file_refs(artifact.get("checkpoint_files", {}))
    if stage == "physical":
        if logical_artifact is None:
            raise ValueError("physical validation requires --logical-artifact")
        _, logical_normalized = load_stage_artifact(logical_artifact, stage="logical")
        logical_graph = TGraph.model_validate(logical_normalized["graph"])
        return ValidationContext(
            preserve_topology_from=logical_graph,
            required_node_fields=["image", "flavor"],
            constraint_files=constraint_files,
            checkpoint_files=checkpoint_files,
            references={"logical": logical_graph},
        )
    return ValidationContext(
        constraint_files=constraint_files,
        checkpoint_files=checkpoint_files,
    )


def _file_refs(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(path) for key, path in value.items()}


def _filter_support_files(artifact: dict[str, Any], text: str) -> dict[str, dict[str, str]]:
    return {
        "constraint_files": _filter_mapping_refs(_file_refs(artifact.get("constraint_files", {})), text),
        "checkpoint_files": _filter_mapping_refs(_file_refs(artifact.get("checkpoint_files", {})), text),
    }


def _filter_mapping_refs(refs: dict[str, str], text: str) -> dict[str, str]:
    needle = text.lower().strip()
    if not needle:
        return refs
    result: dict[str, str] = {}
    for key, value in refs.items():
        haystack = f"{key} {value}".lower()
        if needle in haystack:
            result[key] = value
    return result
