from __future__ import annotations

import ipaddress
from typing import Any

from pydantic import ValidationError

from trace.tools.tgraph.model import TGraphJSON
from trace.tools.tgraph.runtime import TGraphRuntime
from trace.tools.tgraph.validate.issues import issue


def f3_consistency(tgraph: dict[str, Any], **_: Any) -> list[dict[str, Any]]:
    try:
        graph = TGraphJSON.model_validate(TGraphRuntime.from_json(tgraph).to_json())
    except ValidationError:
        return []
    issues: list[dict[str, Any]] = []
    port_owner: dict[str, str] = {}
    port_locations: dict[str, list[str]] = {}

    for node_index, node in enumerate(graph.nodes):
        switch_cidrs: set[str] = set()
        for port_index, port in enumerate(node.ports):
            port_base = f"$.nodes[{node_index}].ports[{port_index}]"
            port_locations.setdefault(port.id, []).append(f"{port_base}.id")
            port_owner[port.id] = node.id

            network_value = None
            ip_value = None
            if port.ip:
                try:
                    ip_value = ipaddress.ip_address(port.ip)
                except ValueError:
                    issues.append(issue("invalid_ip", "ip must be a valid IPv4 address", targets=[f"port:{port.id}"], json_paths=[f"{port_base}.ip"], provenance={"layer": "f3", "source": "builtin"}))
            if port.cidr:
                try:
                    network_value = ipaddress.ip_network(port.cidr, strict=False)
                except ValueError:
                    issues.append(issue("invalid_cidr", "cidr must be a valid CIDR block", targets=[f"port:{port.id}"], json_paths=[f"{port_base}.cidr"], provenance={"layer": "f3", "source": "builtin"}))

            if node.type == "switch":
                if port.ip:
                    issues.append(issue("switch_port_ip_forbidden", "switch ports must not carry host IPs", targets=[f"port:{port.id}"], json_paths=[f"{port_base}.ip"], provenance={"layer": "f3", "source": "builtin"}))
                if not port.cidr:
                    issues.append(issue("invalid_cidr", "switch ports must declare a CIDR", targets=[f"port:{port.id}"], json_paths=[f"{port_base}.cidr"], provenance={"layer": "f3", "source": "builtin"}))
                if network_value is not None:
                    switch_cidrs.add(str(network_value))
            elif node.type == "router" and not port.ip:
                issues.append(issue("router_port_ip_required", "router ports must define IPv4 addresses", targets=[f"port:{port.id}"], json_paths=[f"{port_base}.ip"], provenance={"layer": "f3", "source": "builtin"}))

            if ip_value is not None and network_value is not None and ip_value not in network_value:
                issues.append(issue("ip_not_in_cidr", "ip must belong to cidr", targets=[f"port:{port.id}"], json_paths=[f"{port_base}.ip", f"{port_base}.cidr"], provenance={"layer": "f3", "source": "builtin"}))

        if node.type == "switch" and len(switch_cidrs) > 1:
            issues.append(issue("switch_cidr_mismatch", "all switch ports must share the same cidr", targets=[f"node:{node.id}"], json_paths=[f"$.nodes[{node_index}].ports"], provenance={"layer": "f3", "source": "builtin"}))

    for port_id, paths in port_locations.items():
        if len(paths) > 1:
            issues.append(issue("duplicate_port_id", f"port id '{port_id}' is duplicated", targets=[f"port:{port_id}"], json_paths=paths, provenance={"layer": "f3", "source": "builtin"}))

    seen_links: set[str] = set()
    linked_ports: set[str] = set()
    for link_index, link in enumerate(graph.links):
        link_target = [f"link:{link.id}"]
        if link.id in seen_links:
            issues.append(issue("duplicate_link_id", f"link id '{link.id}' is duplicated", targets=link_target, json_paths=[f"$.links[{link_index}].id"], provenance={"layer": "f3", "source": "builtin"}))
        seen_links.add(link.id)
        expected_id = f"{link.from_port}--{link.to_port}"
        if link.id != expected_id:
            issues.append(issue("link_id_mismatch", "link id must match its endpoint ports", targets=link_target, json_paths=[f"$.links[{link_index}].id"], provenance={"layer": "f3", "source": "builtin"}))
        if link.from_port not in port_owner:
            issues.append(issue("missing_port_reference", "from_port must reference an existing port", targets=link_target, json_paths=[f"$.links[{link_index}].from_port"], provenance={"layer": "f3", "source": "builtin"}))
        if link.to_port not in port_owner:
            issues.append(issue("missing_port_reference", "to_port must reference an existing port", targets=link_target, json_paths=[f"$.links[{link_index}].to_port"], provenance={"layer": "f3", "source": "builtin"}))
        if link.from_port in linked_ports or link.to_port in linked_ports:
            issues.append(issue("port_degree_exceeded", "ports must not participate in more than one link", targets=[f"port:{link.from_port}", f"port:{link.to_port}"], json_paths=[f"$.links[{link_index}]"], provenance={"layer": "f3", "source": "builtin"}))
        linked_ports.add(link.from_port)
        linked_ports.add(link.to_port)

    return issues
