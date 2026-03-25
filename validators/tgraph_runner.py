from __future__ import annotations

import importlib.util
import inspect
from collections import deque
from collections.abc import Iterator, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from app.contracts import ValidationIssue, ValidationReport
from stages.logical.output_schema import CheckpointSpec
from tools.tgraph.validate.f1_format import f1_format
from tools.tgraph.validate.f2_schema import f2_schema
from tools.tgraph.validate.f3_consistency import f3_consistency
from tools.tgraph.validate.f4_intent import f4_intent


ValidatorFn = Callable[..., list[dict[str, Any]]]


BUILTIN_VALIDATORS: dict[str, ValidatorFn] = {
    'f1_format': f1_format,
    'f2_schema': f2_schema,
    'f3_consistency': f3_consistency,
    'f4_intent': f4_intent,
}


def run_tgraph_checks(
    tgraph: dict[str, Any],
    checkpoints: list[dict[str, Any]],
    artifact_root: str | Path,
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    for item in checkpoints:
        checkpoint = CheckpointSpec.model_validate(item)
        try:
            raw_issues = _run_single_checkpoint(tgraph, checkpoint, artifact_root)
            issues.extend(ValidationIssue.model_validate(issue) for issue in raw_issues)
        except Exception as exc:
            issues.append(
                ValidationIssue(
                    code='checkpoint_execution_error',
                    message=f'{checkpoint.id}: {exc}',
                    severity='error',
                    scope='patch',
                    targets=[checkpoint.id],
                    json_paths=[],
                )
            )

    has_errors = any(issue.severity == 'error' for issue in issues)
    return ValidationReport(ok=not has_errors, issues=issues)


def _run_single_checkpoint(
    tgraph: dict[str, Any],
    checkpoint: CheckpointSpec,
    artifact_root: str | Path,
) -> list[dict[str, Any]]:
    if checkpoint.script_ref:
        validator = _load_script_validator(checkpoint, artifact_root)
        target = CheckpointGraphView(tgraph)
    else:
        validator = BUILTIN_VALIDATORS[checkpoint.function_name]
        target = tgraph
    return validator(target, **checkpoint.input_params)


def _load_script_validator(checkpoint: CheckpointSpec, artifact_root: str | Path) -> ValidatorFn:
    script_path = Path(checkpoint.script_ref or '')
    if not script_path.is_absolute() and not script_path.exists():
        script_path = Path(artifact_root) / script_path

    spec = importlib.util.spec_from_file_location('trace_validator', script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f'Could not load validator script: {script_path}')

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    validator = getattr(module, checkpoint.function_name)
    signature = inspect.signature(validator)

    def invoke(_graph_target: Any, **kwargs: Any) -> list[dict[str, Any]]:
        setattr(module, 'tgraph', _graph_target)
        setattr(module, 'graph', _graph_target)
        setattr(module, 'logical', SimpleNamespace(tgraph_logical=_graph_target))
        setattr(module, 'physical', SimpleNamespace(tgraph_physical=_graph_target))
        if _script_expects_graph(signature, kwargs):
            return validator(_graph_target, **kwargs)
        return validator(**kwargs)

    return invoke


def _script_expects_graph(signature: inspect.Signature, kwargs: dict[str, Any]) -> bool:
    params = list(signature.parameters.values())
    if not params:
        return False
    first = params[0]
    if first.kind in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}:
        return True
    if first.name in {'tgraph', 'graph', 'payload'}:
        return True
    if first.name not in kwargs:
        return True
    return False


class CheckpointGraphView(Mapping[str, Any]):
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self._nodes = {node.get('id'): node for node in payload.get('nodes', [])}
        self._port_owner = self._build_port_owner(payload)
        self._adjacency = self._build_adjacency(payload)

    def __getitem__(self, key: str) -> Any:
        return self._payload[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._payload)

    def __len__(self) -> int:
        return len(self._payload)

    @property
    def nodes(self) -> list[dict[str, Any]]:
        return self._payload.get('nodes', [])

    @property
    def links(self) -> list[dict[str, Any]]:
        return self._payload.get('links', [])

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        return self._nodes.get(node_id)

    def get_link(self, link_id: str) -> dict[str, Any] | None:
        for link in self._payload.get('links', []):
            if link.get('id') == link_id:
                return link
        return None

    def list_links(self, node_id: str | None = None, port_id: str | None = None) -> list[dict[str, Any]]:
        links = self._payload.get('links', [])
        if node_id is None and port_id is None:
            return links

        results: list[dict[str, Any]] = []
        for link in links:
            from_node = link.get('from_node') or self._port_owner.get(link.get('from_port', ''))
            to_node = link.get('to_node') or self._port_owner.get(link.get('to_port', ''))
            endpoints = {link.get('from_port'), link.get('to_port')}
            if node_id is not None and node_id not in {from_node, to_node}:
                continue
            if port_id is not None and port_id not in endpoints:
                continue
            results.append(link)
        return results

    def get_links_for_node(self, node_id: str) -> list[dict[str, Any]]:
        return self.list_links(node_id=node_id)

    def get_links(self, node_id: str) -> list[dict[str, Any]]:
        return self.get_links_for_node(node_id)

    def find_paths(self, source_id: str, target_id: str, max_paths: int = 64) -> list[list[str]]:
        if source_id not in self._nodes or target_id not in self._nodes:
            return []
        if source_id == target_id:
            return [[source_id]]

        paths: list[list[str]] = []
        queue: deque[list[str]] = deque([[source_id]])
        while queue and len(paths) < max_paths:
            path = queue.popleft()
            current = path[-1]
            for neighbor in sorted(self._adjacency.get(current, set())):
                if neighbor in path:
                    continue
                next_path = [*path, neighbor]
                if neighbor == target_id:
                    paths.append(next_path)
                    continue
                queue.append(next_path)
        return paths

    def find_path(self, source_id: str, target_ids: str | list[str]) -> list[str]:
        if isinstance(target_ids, str):
            return [target_ids] if self.check_reachability(source_id, target_ids) else []
        return [target_id for target_id in target_ids if self.check_reachability(source_id, target_id)]

    def is_reachable(self, source_id: str, target_id: str, via: str | None = None) -> bool:
        if via is None:
            return self.check_reachability(source_id, target_id)
        return self.check_reachability(source_id, via) and self.check_reachability(via, target_id)

    def check_reachability(self, source_id: str, target_id: str) -> bool:
        if source_id not in self._nodes or target_id not in self._nodes:
            return False
        queue: deque[str] = deque([source_id])
        visited = {source_id}
        while queue:
            current = queue.popleft()
            if current == target_id:
                return True
            for neighbor in self._adjacency.get(current, set()):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append(neighbor)
        return False

    @staticmethod
    def _build_port_owner(payload: dict[str, Any]) -> dict[str, str]:
        owners: dict[str, str] = {}
        for node in payload.get('nodes', []):
            node_id = node.get('id', '')
            for port in node.get('ports', []):
                owners[port.get('id', '')] = node_id
        return owners

    def _build_adjacency(self, payload: dict[str, Any]) -> dict[str, set[str]]:
        adjacency: dict[str, set[str]] = {node_id: set() for node_id in self._nodes}
        for link in payload.get('links', []):
            from_node = link.get('from_node') or self._port_owner.get(link.get('from_port', ''))
            to_node = link.get('to_node') or self._port_owner.get(link.get('to_port', ''))
            if not from_node or not to_node:
                continue
            adjacency.setdefault(from_node, set()).add(to_node)
            adjacency.setdefault(to_node, set()).add(from_node)
        return adjacency
