from __future__ import annotations

from collections import Counter

from tgraph.core.graph import TGraph
from tgraph.operations.validate.issues import ValidationIssue


def f3_graph(graph: TGraph) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    node_ids = [node.id for node in graph.nodes]
    for node_id, count in Counter(node_ids).items():
        if count > 1:
            issues.append(
                ValidationIssue(
                    code="duplicate_node_id",
                    message=f"node id appears more than once: {node_id}",
                    location=f"nodes.{node_id}",
                )
            )

    port_ids: list[str] = []
    port_owner: dict[str, str] = {}
    for node in graph.nodes:
        for port in node.ports:
            port_ids.append(port.id)
            port_owner.setdefault(port.id, node.id)
    for port_id, count in Counter(port_ids).items():
        if count > 1:
            issues.append(
                ValidationIssue(
                    code="duplicate_port_id",
                    message=f"port id appears more than once: {port_id}",
                    location=f"ports.{port_id}",
                )
            )

    degree: Counter[str] = Counter()
    link_ids = [link.id for link in graph.links]
    for link_id, count in Counter(link_ids).items():
        if count > 1:
            issues.append(
                ValidationIssue(
                    code="duplicate_link_id",
                    message=f"link id appears more than once: {link_id}",
                    location=f"links.{link_id}",
                )
            )

    for link in graph.links:
        if link.from_port not in port_owner:
            issues.append(
                ValidationIssue(
                    code="unknown_link_port",
                    message=f"link references unknown from_port: {link.from_port}",
                    location=f"links.{link.id}.from_port",
                )
            )
        if link.to_port not in port_owner:
            issues.append(
                ValidationIssue(
                    code="unknown_link_port",
                    message=f"link references unknown to_port: {link.to_port}",
                    location=f"links.{link.id}.to_port",
                )
            )
        expected_id = _link_id(link.from_port, link.to_port)
        if link.id != expected_id:
            issues.append(
                ValidationIssue(
                    code="noncanonical_link_id",
                    message=f"link id must be {expected_id}",
                    location=f"links.{link.id}.id",
                )
            )
        degree[link.from_port] += 1
        degree[link.to_port] += 1

    for port_id, count in degree.items():
        if count > 1:
            issues.append(
                ValidationIssue(
                    code="port_degree_exceeded",
                    message=f"port is connected to more than one link: {port_id}",
                    location=f"ports.{port_id}",
                )
            )

    return issues


def _link_id(port_a: str, port_b: str) -> str:
    a, b = sorted((port_a, port_b))
    return f"{a}--{b}"

