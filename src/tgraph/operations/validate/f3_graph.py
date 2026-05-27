from __future__ import annotations

from collections import Counter
import re

from tgraph.core.graph import TGraph
from tgraph.operations.validate.issues import ValidationIssue, validation_issue

_LINK_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")


def f3_graph(graph: TGraph) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    node_ids = [node.id for node in graph.nodes]
    for node_id, count in Counter(node_ids).items():
        if count > 1:
            issues.append(
                validation_issue(
                    "duplicate_node_id",
                    f"node id appears more than once: {node_id}",
                    location=f"nodes.{node_id}",
                )
            )

    ports_by_node: dict[str, set[str]] = {}
    for node in graph.nodes:
        node_port_ids = [port.id for port in node.ports]
        ports_by_node[node.id] = set(node_port_ids)
        for port_id, count in Counter(node_port_ids).items():
            if count > 1:
                issues.append(
                    validation_issue(
                        "duplicate_port_id",
                        f"port id appears more than once on node {node.id}: {port_id}",
                        location=f"nodes.{node.id}.ports.{port_id}",
                    )
                )

    degree: Counter[tuple[str, str]] = Counter()
    link_ids = [link.id for link in graph.links]
    for link_id, count in Counter(link_ids).items():
        if count > 1:
            issues.append(
                validation_issue(
                    "duplicate_link_id",
                    f"link id appears more than once: {link_id}",
                    location=f"links.{link_id}",
                )
            )

    for link in graph.links:
        if link.from_node not in ports_by_node:
            issues.append(
                validation_issue(
                    "unknown_link_node",
                    f"link references unknown from_node: {link.from_node}",
                    location=f"links.{link.id}.from_node",
                )
            )
        elif link.from_port not in ports_by_node[link.from_node]:
            issues.append(
                validation_issue(
                    "unknown_link_port",
                    f"link references unknown from endpoint: {link.from_node}.{link.from_port}",
                    location=f"links.{link.id}.from_port",
                )
            )

        if link.to_node not in ports_by_node:
            issues.append(
                validation_issue(
                    "unknown_link_node",
                    f"link references unknown to_node: {link.to_node}",
                    location=f"links.{link.id}.to_node",
                )
            )
        elif link.to_port not in ports_by_node[link.to_node]:
            issues.append(
                validation_issue(
                    "unknown_link_port",
                    f"link references unknown to endpoint: {link.to_node}.{link.to_port}",
                    location=f"links.{link.id}.to_port",
                )
            )

        if not _link_id_matches_endpoint(link.id, link.from_node, link.to_node):
            node_a, node_b = sorted((link.from_node, link.to_node))
            issues.append(
                validation_issue(
                    "noncanonical_link_id",
                    f"link id must start with {node_a}-{node_b}- and use a key without '-'",
                    location=f"links.{link.id}.id",
                )
            )

        degree[(link.from_node, link.from_port)] += 1
        degree[(link.to_node, link.to_port)] += 1

    for (node_id, port_id), count in degree.items():
        if count > 1:
            issues.append(
                validation_issue(
                    "port_degree_exceeded",
                    f"port is connected to more than one link: {node_id}.{port_id}",
                    location=f"nodes.{node_id}.ports.{port_id}",
                )
            )

    return issues


def _link_id_matches_endpoint(link_id: str, from_node: str, to_node: str) -> bool:
    node_a, node_b = sorted((from_node, to_node))
    prefix = f"{node_a}-{node_b}-"
    if not link_id.startswith(prefix):
        return False
    key = link_id.removeprefix(prefix)
    return bool(key) and _LINK_KEY_RE.match(key) is not None
