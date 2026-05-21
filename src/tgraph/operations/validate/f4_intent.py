from __future__ import annotations

from tgraph.core.graph import Link, TGraph
from tgraph.operations.validate.issues import ValidationIssue
from tgraph.operations.validate.policy import ValidationContext


def f4_intent(graph: TGraph, context: ValidationContext | None = None) -> list[ValidationIssue]:
    if context is None:
        return []

    issues: list[ValidationIssue] = []
    if context.preserve_topology_from is not None:
        issues.extend(_preserve_topology(graph, context.preserve_topology_from))

    issues.extend(_required_node_fields(graph, context.required_node_fields))
    issues.extend(_required_link_fields(graph, context.required_link_fields))
    return issues


def _preserve_topology(graph: TGraph, source: TGraph) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    graph_node_ids = {node.id for node in graph.nodes}
    for node in source.nodes:
        if node.id not in graph_node_ids:
            issues.append(
                ValidationIssue(
                    code="missing_preserved_node",
                    message=f"graph is missing preserved node: {node.id}",
                    location=f"nodes.{node.id}",
                )
            )

    graph_pairs = _node_pairs(graph)
    for pair in _node_pairs(source):
        if pair not in graph_pairs:
            issues.append(
                ValidationIssue(
                    code="missing_preserved_link",
                    message=f"graph is missing preserved link between {pair[0]} and {pair[1]}",
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
                    ValidationIssue(
                        code="missing_required_node_field",
                        message=f"node {node.id} is missing required field: {field}",
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
                    ValidationIssue(
                        code="missing_required_link_field",
                        message=f"link {link.id} is missing required field: {field}",
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

