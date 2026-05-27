from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from tgraph.core.graph import Link, TGraph
from tgraph.operations.validate.checkpoint_files import execute_checkpoint_file
from tgraph.operations.validate.constraint_files import load_constraint_file
from tgraph.operations.validate.issues import ValidationIssue, validation_issue
from tgraph.operations.validate.policy import ValidationContext


def f4_intent(graph: TGraph, context: ValidationContext | None = None) -> list[ValidationIssue]:
    if context is None:
        return []

    issues: list[ValidationIssue] = []
    if context.preserve_topology_from is not None:
        issues.extend(_preserve_topology(graph, context.preserve_topology_from))

    issues.extend(_required_node_fields(graph, context.required_node_fields))
    issues.extend(_required_link_fields(graph, context.required_link_fields))
    issues.extend(_run_checkpoint_files(graph, context))
    return issues


def _run_checkpoint_files(graph: TGraph, context: ValidationContext) -> list[ValidationIssue]:
    if not context.constraint_files and not context.checkpoint_files:
        return []

    issues: list[ValidationIssue] = []
    executions: list[tuple[dict[str, object], str | Path]] = []
    scopes = sorted(set(context.constraint_files) | set(context.checkpoint_files))
    for scope in scopes:
        normalized_scope = _constraint_scope(scope)
        constraint_path = context.constraint_files.get(scope)
        checkpoint_path = context.checkpoint_files.get(scope)
        if normalized_scope is None:
            issues.append(
                validation_issue(
                    "constraint.file.invalid_scope",
                    f"unknown constraint/checkpoint file scope: {scope}",
                    location=str(scope),
                    details={"scope": str(scope)},
                )
            )
            continue
        if constraint_path is None:
            issues.append(
                validation_issue(
                    "checkpoint.file.missing_constraint_file",
                    f"checkpoint file scope {scope} has no matching constraint file",
                    location=str(checkpoint_path),
                    details={"scope": scope, "checkpoint_path": str(checkpoint_path)},
                )
            )
            continue

        constraint_result = load_constraint_file(constraint_path, scope=normalized_scope)
        issues.extend(constraint_result.issues)
        if not constraint_result.ok:
            continue
        if not constraint_result.constraints and checkpoint_path is None:
            continue
        if checkpoint_path is None:
            issues.append(
                validation_issue(
                    "checkpoint.file.missing_checkpoint_file",
                    f"constraint file scope {scope} has no matching checkpoint file",
                    location=str(constraint_path),
                    details={"scope": scope, "constraint_path": str(constraint_path)},
                )
            )
            continue

        executions.append((constraint_result.constraints, checkpoint_path))

    max_workers = max(1, int(context.checkpoint_max_processes))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                execute_checkpoint_file,
                graph,
                constraints=constraints,
                checkpoint_path=checkpoint_path,
                references=context.references,
                timeout_seconds=context.checkpoint_timeout_seconds,
            )
            for constraints, checkpoint_path in executions
        ]
        for future in futures:
            issues.extend(future.result().issues)
    return issues


def _constraint_scope(scope: str) -> Literal["logical", "physical"] | None:
    if scope in {"logical", "physical"}:
        return scope
    return None


def _preserve_topology(graph: TGraph, source: TGraph) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    graph_node_ids = {node.id for node in graph.nodes}
    for node in source.nodes:
        if node.id not in graph_node_ids:
            issues.append(
                validation_issue(
                    "missing_preserved_node",
                    f"graph is missing preserved node: {node.id}",
                    location=f"nodes.{node.id}",
                )
            )

    graph_pairs = _node_pairs(graph)
    for pair in _node_pairs(source):
        if pair not in graph_pairs:
            issues.append(
                validation_issue(
                    "missing_preserved_link",
                    f"graph is missing preserved link between {pair[0]} and {pair[1]}",
                    location=f"links.{pair[0]}--{pair[1]}",
                )
            )
    return issues


def _required_node_fields(graph: TGraph, fields: list[str]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for node in graph.nodes:
        for field in fields:
            if not getattr(node, field, None):
                issues.append(
                    validation_issue(
                        "missing_required_node_field",
                        f"node {node.id} is missing required field: {field}",
                        location=f"nodes.{node.id}.{field}",
                    )
                )
    return issues


def _required_link_fields(graph: TGraph, fields: list[str]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for link in graph.links:
        for field in fields:
            if not getattr(link, field, None):
                issues.append(
                    validation_issue(
                        "missing_required_link_field",
                        f"link {link.id} is missing required field: {field}",
                        location=f"links.{link.id}.{field}",
                    )
                )
    return issues


def _node_pairs(graph: TGraph) -> set[tuple[str, str]]:
    port_owner = {
        port.id: node.id
        for node in graph.nodes
        for port in node.ports
    }
    pairs: set[tuple[str, str]] = set()
    for link in graph.links:
        node_a, node_b = _link_nodes(link, port_owner)
        if node_a and node_b:
            pairs.add(tuple(sorted((node_a, node_b))))
    return pairs


def _link_nodes(link: Link, port_owner: dict[str, str]) -> tuple[str | None, str | None]:
    return (
        link.from_node or port_owner.get(link.from_port),
        link.to_node or port_owner.get(link.to_port),
    )
