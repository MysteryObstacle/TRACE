from __future__ import annotations

import ipaddress
from typing import Any

from tools.tgraph.model import TGraph
from tools.tgraph.validate.issues import issue


def f3_consistency(tgraph: dict[str, Any], **_: Any) -> list[dict[str, Any]]:
    graph = TGraph.model_validate(tgraph)
    issues: list[dict[str, Any]] = []

    node_locations: dict[str, list[str]] = {}
    port_locations: dict[str, list[str]] = {}
    link_locations: dict[str, list[str]] = {}
    port_owner: dict[str, str] = {}
    cidr_ip_locations: dict[tuple[str, str], list[str]] = {}
    port_link_locations: dict[str, list[str]] = {}

    for node_index, node in enumerate(graph.nodes):
        node_path = f"$.nodes[{node_index}].id"
        node_locations.setdefault(node.id, []).append(node_path)
        switch_cidrs: set[str] = set()

        for port_index, port in enumerate(node.ports):
            port_base_path = f"$.nodes[{node_index}].ports[{port_index}]"
            port_locations.setdefault(port.id, []).append(f"{port_base_path}.id")
            port_owner.setdefault(port.id, node.id)

            ip_value = None
            network_value = None

            if port.ip:
                try:
                    ip_value = ipaddress.ip_address(port.ip)
                except ValueError:
                    issues.append(issue("invalid_ip", "ip must be a valid IPv4 address", "port", targets=[f"port:{port.id}"], json_paths=[f"{port_base_path}.ip"]))

            if port.cidr:
                try:
                    network_value = ipaddress.ip_network(port.cidr, strict=False)
                except ValueError:
                    issues.append(issue("invalid_cidr", "cidr must be a valid CIDR block", "port", targets=[f"port:{port.id}"], json_paths=[f"{port_base_path}.cidr"]))

            if node.type == "switch":
                if port.ip:
                    issues.append(issue("switch_port_ip_forbidden", "switch ports must not carry host IPs", "port", targets=[f"port:{port.id}"], json_paths=[f"{port_base_path}.ip"]))
                if not port.cidr:
                    issues.append(issue("invalid_cidr", "switch ports must declare a CIDR", "port", targets=[f"port:{port.id}"], json_paths=[f"{port_base_path}.cidr"]))
                if network_value is not None:
                    switch_cidrs.add(str(network_value))
            elif node.type == "router":
                if not port.ip:
                    issues.append(issue("router_port_ip_required", "router ports must define IPv4 addresses", "port", targets=[f"port:{port.id}"], json_paths=[f"{port_base_path}.ip"]))

            if ip_value is not None and network_value is not None:
                if ip_value not in network_value:
                    issues.append(issue("ip_not_in_cidr", "ip must belong to cidr", "port", targets=[f"port:{port.id}"], json_paths=[f"{port_base_path}.ip", f"{port_base_path}.cidr"]))
                elif node.type in {"router", "computer"}:
                    cidr_ip_locations.setdefault((str(network_value), str(ip_value)), []).append(f"{port_base_path}.ip")

        if node.type == "switch" and len(switch_cidrs) > 1:
            issues.append(issue("switch_cidr_mismatch", "all switch ports must share the same cidr", "node", targets=[f"node:{node.id}"], json_paths=[f"$.nodes[{node_index}].ports"]))

    for node_id, paths in node_locations.items():
        if len(paths) > 1:
            issues.append(issue("duplicate_node_id", f"node id '{node_id}' is duplicated", "node", targets=[f"node:{node_id}"], json_paths=paths))

    for port_id, paths in port_locations.items():
        if len(paths) > 1:
            issues.append(issue("duplicate_port_id", f"port id '{port_id}' is duplicated", "port", targets=[f"port:{port_id}"], json_paths=paths))

    for link_index, link in enumerate(graph.links):
        link_locations.setdefault(link.id, []).append(f"$.links[{link_index}].id")
        expected_id = f"{link.from_port}--{link.to_port}"
        target = [f"link:{link.id}"]

        if link.id != expected_id:
            issues.append(issue("link_id_mismatch", "link id must match its endpoint ports", "link", targets=target, json_paths=[f"$.links[{link_index}].id"]))

        from_owner = port_owner.get(link.from_port)
        to_owner = port_owner.get(link.to_port)
        port_link_locations.setdefault(link.from_port, []).append(f"$.links[{link_index}].from_port")
        port_link_locations.setdefault(link.to_port, []).append(f"$.links[{link_index}].to_port")

        if from_owner is None:
            issues.append(issue("missing_port_reference", "from_port must reference an existing port", "link", targets=target + [f"port:{link.from_port}"], json_paths=[f"$.links[{link_index}].from_port"]))
        if to_owner is None:
            issues.append(issue("missing_port_reference", "to_port must reference an existing port", "link", targets=target + [f"port:{link.to_port}"], json_paths=[f"$.links[{link_index}].to_port"]))

        if from_owner is not None and link.from_node is not None and link.from_node != from_owner:
            issues.append(issue("link_node_owner_mismatch", "from_node must match the owning node of from_port", "link", targets=target, json_paths=[f"$.links[{link_index}].from_node"]))
        if to_owner is not None and link.to_node is not None and link.to_node != to_owner:
            issues.append(issue("link_node_owner_mismatch", "to_node must match the owning node of to_port", "link", targets=target, json_paths=[f"$.links[{link_index}].to_node"]))

    for link_id, paths in link_locations.items():
        if len(paths) > 1:
            issues.append(issue("duplicate_link_id", f"link id '{link_id}' is duplicated", "link", targets=[f"link:{link_id}"], json_paths=paths))

    for port_id, paths in port_link_locations.items():
        if len(paths) > 1:
            issues.append(
                issue(
                    "port_degree_exceeded",
                    f"port '{port_id}' must not participate in more than one link",
                    "port",
                    targets=[f"port:{port_id}"],
                    json_paths=paths,
                )
            )

    for (cidr, ip_value), paths in cidr_ip_locations.items():
        if len(paths) > 1:
            issues.append(issue("duplicate_ip_in_cidr", f"ip '{ip_value}' is duplicated in cidr '{cidr}'", "port", json_paths=paths))

    return issues
