from __future__ import annotations

import ipaddress

from tools.tgraph.model import Port, TGraph, ensure_tgraph


def get_port(graph: TGraph | dict, port_id: str) -> Port:
    model = ensure_tgraph(graph)
    indexes = model.build_indexes()
    if port_id not in indexes.port_by_id:
        raise KeyError(f"query_port_not_found:{port_id}")
    return indexes.port_by_id[port_id]


def owner_of(graph: TGraph | dict, port_id: str) -> str:
    model = ensure_tgraph(graph)
    indexes = model.build_indexes()
    if port_id not in indexes.port_owner:
        raise KeyError(f"query_port_not_found:{port_id}")
    return indexes.port_owner[port_id]


def ports_in_cidr(graph: TGraph | dict, cidr: str) -> list[str]:
    try:
        network = ipaddress.ip_network(cidr, strict=False)
    except ValueError as exc:
        raise ValueError(f"query_invalid_cidr:{cidr}") from exc

    model = ensure_tgraph(graph)
    matches: list[str] = []
    for node in model.nodes:
        for port in node.ports:
            if not port.ip:
                continue
            try:
                ip_value = ipaddress.ip_address(port.ip)
            except ValueError:
                continue
            if ip_value in network:
                matches.append(port.id)
    return matches
