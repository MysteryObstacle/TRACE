from __future__ import annotations

import copy
import ipaddress
from collections import deque
from itertools import product
from typing import Any, Mapping

from tgraph.core.graph import TGraph
from tgraph.operations.validate.escalation_kinds import ESCALATION_ISSUE_KINDS


def issue(
    issue_kind: str,
    message: str,
    *,
    severity: str = "error",
    location: str | None = None,
    targets: list[str] | None = None,
    fact_kind: str | None = None,
    repair_target: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload_details = dict(details or {})
    payload_details.setdefault("issue_kind", issue_kind)
    if fact_kind is not None:
        payload_details.setdefault("fact_kind", fact_kind)
    if repair_target is not None:
        payload_details.setdefault("repair_target", repair_target)
    if targets:
        payload_details.setdefault("targets", list(targets))
    return {
        "message": message,
        "severity": severity,
        "location": location,
        "details": payload_details,
    }


class TGraphView:
    def __init__(self, graph: TGraph | dict[str, Any], *, references: Mapping[str, TGraph | dict[str, Any]] | None = None) -> None:
        self._graph = graph if isinstance(graph, TGraph) else TGraph.model_validate(graph)
        self._references = {
            str(name): value if isinstance(value, TGraph) else TGraph.model_validate(value)
            for name, value in (references or {}).items()
        }
        self._reference_views: dict[str, TGraphView] = {}

        self._nodes_by_id = {node.id: node for node in self._graph.nodes}
        self._node_payloads = {node.id: node.model_dump(mode="json") for node in self._graph.nodes}

        self._ports_by_node: dict[str, dict[str, dict[str, Any]]] = {}
        for node in self._graph.nodes:
            node_ports: dict[str, dict[str, Any]] = {}
            for port in node.ports:
                payload = port.model_dump(mode="json")
                node_ports[port.id] = payload
            self._ports_by_node[node.id] = node_ports

        self._links_by_id: dict[str, dict[str, Any]] = {}
        for link in self._graph.links:
            payload = link.model_dump(mode="json")
            self._links_by_id[link.id] = payload

        self._adjacency = self._build_adjacency()

    @property
    def stage(self) -> str:
        return self._graph.stage

    def document(self) -> dict[str, Any]:
        return self._graph.model_dump(mode="json")

    def reference(self, name: str) -> TGraphView | None:
        key = str(name)
        if key not in self._references:
            return None
        if key not in self._reference_views:
            self._reference_views[key] = TGraphView(self._references[key])
        return self._reference_views[key]

    def node(self, node_id: str) -> dict[str, Any] | None:
        payload = self._node_payloads.get(str(node_id))
        return copy.deepcopy(payload) if payload is not None else None

    def nodes(
        self,
        *,
        type: str | None = None,
        ids: list[str] | None = None,
        selector: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        allowed = set(str(item) for item in ids) if ids is not None else None
        expected = dict(selector or {})
        selected: list[dict[str, Any]] = []
        for node_id, payload in self._node_payloads.items():
            if allowed is not None and node_id not in allowed:
                continue
            if type is not None and payload.get("type") != type:
                continue
            if any(payload.get(key) != value for key, value in expected.items()):
                continue
            selected.append(copy.deepcopy(payload))
        return selected

    def port(self, node_id: str, port_id: str) -> dict[str, Any] | None:
        payload = self._ports_by_node.get(str(node_id), {}).get(str(port_id))
        if payload is None:
            return None
        enriched = copy.deepcopy(payload)
        enriched["node"] = str(node_id)
        return enriched

    def ports(self, *, node_id: str | None = None, cidr: str | None = None) -> list[dict[str, Any]]:
        expected_cidr = _canonical_cidr(cidr)
        selected: list[dict[str, Any]] = []
        for owner, ports in self._ports_by_node.items():
            if node_id is not None and owner != node_id:
                continue
            for payload in ports.values():
                if expected_cidr and _canonical_cidr(payload.get("cidr")) != expected_cidr:
                    continue
                enriched = copy.deepcopy(payload)
                enriched["node"] = owner
                selected.append(enriched)
        return selected

    def link(self, link_id: str) -> dict[str, Any] | None:
        payload = self._links_by_id.get(str(link_id))
        return copy.deepcopy(payload) if payload is not None else None

    def links(
        self,
        *,
        node_id: str | None = None,
        port_id: str | None = None,
        between: list[str] | tuple[str, str] | None = None,
        link_key: str | None = None,
    ) -> list[dict[str, Any]]:
        pair = None
        if between is not None:
            pair = tuple(sorted(str(item) for item in between))
        selected: list[dict[str, Any]] = []
        for payload in self._links_by_id.values():
            nodes = {str(payload.get("from_node") or ""), str(payload.get("to_node") or "")}
            if node_id is not None and node_id not in nodes:
                continue
            if port_id is not None and not _link_has_endpoint(payload, node_id=node_id, port_id=str(port_id)):
                continue
            if pair is not None and tuple(sorted(nodes - {""})) != pair:
                continue
            if link_key is not None and not _link_matches_key(payload, str(link_key)):
                continue
            selected.append(copy.deepcopy(payload))
        return selected

    def neighbors(self, node_id: str) -> list[str]:
        return sorted(self._adjacency.get(str(node_id), set()))

    def degree(self, node_id: str) -> int:
        return len(self._adjacency.get(str(node_id), set()))

    def connected(self, node_a: str, node_b: str) -> bool:
        return str(node_b) in self._adjacency.get(str(node_a), set())

    def path_exists(self, source: str, target: str, *, max_hops: int | None = None) -> bool:
        return bool(self.paths(source, target, max_hops=max_hops, limit=1))

    def paths(self, source: str, target: str, *, max_hops: int | None = None, limit: int = 20) -> list[list[str]]:
        source_id = str(source)
        target_id = str(target)
        if source_id not in self._adjacency or target_id not in self._adjacency:
            return []

        cutoff = max_hops if max_hops is not None else max(len(self._adjacency) - 1, 0)
        found: list[list[str]] = []

        def dfs(current: str, path: list[str]) -> None:
            if len(found) >= limit:
                return
            if len(path) - 1 > cutoff:
                return
            if current == target_id:
                found.append(path[:])
                return
            for neighbor in sorted(self._adjacency.get(current, set())):
                if neighbor in path:
                    continue
                path.append(neighbor)
                dfs(neighbor, path)
                path.pop()

        dfs(source_id, [source_id])
        return found

    def all_paths_include(self, source: str, target: str, required_nodes: list[str], *, max_hops: int | None = None) -> bool:
        required = {str(item) for item in required_nodes}
        paths = self.paths(source, target, max_hops=max_hops)
        return bool(paths) and all(required.issubset(set(path)) for path in paths)

    def any_path_include(self, source: str, target: str, required_nodes: list[str], *, max_hops: int | None = None) -> bool:
        required = {str(item) for item in required_nodes}
        return any(required.issubset(set(path)) for path in self.paths(source, target, max_hops=max_hops))

    def all_paths_exclude(self, source: str, target: str, forbidden_nodes: list[str], *, max_hops: int | None = None) -> bool:
        forbidden = {str(item) for item in forbidden_nodes}
        paths = self.paths(source, target, max_hops=max_hops)
        return bool(paths) and all(forbidden.isdisjoint(path) for path in paths)

    def group_paths_include(
        self,
        sources: list[str],
        targets: list[str],
        required_nodes: list[str],
        *,
        max_hops: int | None = None,
    ) -> bool:
        return all(
            self.all_paths_include(source, target, required_nodes, max_hops=max_hops)
            for source, target in product(sources, targets)
        )

    def group_isolated(self, sources: list[str], targets: list[str], *, max_hops: int | None = None) -> bool:
        return all(
            not self.path_exists(source, target, max_hops=max_hops)
            for source, target in product(sources, targets)
        )

    def cidrs(self) -> list[str]:
        values = {
            _canonical_cidr(payload.get("cidr"))
            for ports in self._ports_by_node.values()
            for payload in ports.values()
            if payload.get("cidr")
        }
        return sorted(value for value in values if value)

    def ports_in_cidr(self, cidr: str) -> list[dict[str, Any]]:
        return self.ports(cidr=cidr)

    def nodes_in_cidr(self, cidr: str) -> list[dict[str, Any]]:
        expected = _canonical_cidr(cidr)
        node_ids = {
            owner
            for owner, ports in self._ports_by_node.items()
            for port in ports.values()
            if _canonical_cidr(port.get("cidr")) == expected
        }
        return [self.node(node_id) for node_id in sorted(node_ids) if self.node(node_id) is not None]

    def node_has_port_in_cidr(self, node_id: str, cidr: str, ip: str | None = None) -> bool:
        expected_cidr = _canonical_cidr(cidr)
        expected_ip = str(ip or "").strip()
        for port in self.ports(node_id=str(node_id)):
            if _canonical_cidr(port.get("cidr")) != expected_cidr:
                continue
            if expected_ip and str(port.get("ip") or "").strip() != expected_ip:
                continue
            return True
        return False

    def ports_share_cidr(
        self,
        *,
        port_ids: list[str] | None = None,
        node_ids: list[str] | None = None,
        cidr: str | None = None,
    ) -> bool:
        selected: list[dict[str, Any]] = []
        if port_ids is not None:
            wanted = {str(item) for item in port_ids}
            for node_id in sorted(self._ports_by_node):
                for port_id in sorted(self._ports_by_node[node_id]):
                    if port_id in wanted:
                        selected.append(self.port(node_id, port_id))
        elif node_ids is not None:
            for node_id in node_ids:
                selected.extend(self.ports(node_id=str(node_id)))
        else:
            selected = self.ports()

        if not selected:
            return False

        canonical = {_canonical_cidr(port.get("cidr")) for port in selected}
        canonical.discard("")
        if not canonical:
            return False
        if cidr is not None:
            return canonical == {_canonical_cidr(cidr)}
        return len(canonical) == 1

    def switch_cidr(self, switch_id: str) -> str | None:
        node = self.node(switch_id)
        if node is None or node.get("type") != "switch":
            return None
        cidrs = {_canonical_cidr(port.get("cidr")) for port in node.get("ports", []) if port.get("cidr")}
        cidrs.discard("")
        if len(cidrs) != 1:
            return None
        return next(iter(cidrs))

    def ip_in_cidr(self, ip: str, cidr: str) -> bool:
        try:
            return ipaddress.ip_address(str(ip)) in ipaddress.ip_network(str(cidr), strict=False)
        except ValueError:
            return False

    def topology_pairs(self) -> set[tuple[str, str]]:
        pairs: set[tuple[str, str]] = set()
        for payload in self._links_by_id.values():
            node_a = str(payload.get("from_node") or "")
            node_b = str(payload.get("to_node") or "")
            if node_a and node_b:
                pairs.add(tuple(sorted((node_a, node_b))))
        return pairs

    def node_ids(self) -> set[str]:
        return set(self._nodes_by_id)

    def issue(
        self,
        issue_kind: str,
        message: str,
        *,
        severity: str = "error",
        location: str | None = None,
        targets: list[str] | None = None,
        fact_kind: str | None = None,
        repair_target: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return issue(
            issue_kind,
            message,
            severity=severity,
            location=location,
            targets=targets,
            fact_kind=fact_kind,
            repair_target=repair_target,
            details=details,
        )

    def escalate(
        self,
        issue_kind: str,
        message: str,
        *,
        targets: list[str] | None = None,
        fact_kind: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if issue_kind not in ESCALATION_ISSUE_KINDS:
            raise ValueError(f"unsupported escalation issue kind: {issue_kind}")
        return [
            self.issue(
                issue_kind,
                message,
                targets=targets,
                fact_kind=fact_kind,
                repair_target="constraint",
                details=details,
            )
        ]

    def check_subnet(self, switch: str, cidr: str) -> list[dict[str, Any]]:
        fact_kind = "logical.addressing.subnet"
        expected_cidr = _canonical_cidr(cidr)
        node = self.node(switch)
        if node is None:
            return [
                _fact_issue(
                    fact_kind,
                    "missing_node",
                    f"{switch} must exist for subnet {expected_cidr}",
                    targets=[switch],
                    details={"expected_cidr": expected_cidr},
                )
            ]

        ports = self.ports(node_id=switch)
        if not ports:
            return [
                _fact_issue(
                    fact_kind,
                    "no_ports",
                    f"{switch} must have ports in {expected_cidr}",
                    targets=[switch],
                    details={"expected_cidr": expected_cidr},
                )
            ]

        mismatched = [
            {"port": port.get("id"), "actual_cidr": _canonical_cidr(port.get("cidr"))}
            for port in ports
            if _canonical_cidr(port.get("cidr")) != expected_cidr
        ]
        if mismatched:
            return [
                _fact_issue(
                    fact_kind,
                    "cidr_mismatch",
                    f"all {switch} ports must use CIDR {expected_cidr}",
                    targets=[switch],
                    details={"expected_cidr": expected_cidr, "mismatched_ports": mismatched},
                )
            ]
        return []

    def check_interface(self, node: str, *, segment: str, cidr: str | None = None, ip: str | None = None, link_key: str | None = None) -> list[dict[str, Any]]:
        fact_kind = "logical.addressing.interface"
        links = self.links(between=[node, segment], link_key=link_key)
        if not links:
            return [
                _fact_issue(
                    fact_kind,
                    "missing_link",
                    f"{node} must connect directly to {segment}",
                    targets=[node, segment],
                    details={"expected_edge": [node, segment], "expected_link_key": link_key},
                )
            ]

        expected_cidr = _canonical_cidr(cidr)
        for link in links:
            node_port = _endpoint_port(self, link, node)
            segment_port = _endpoint_port(self, link, segment)
            if node_port is None or segment_port is None:
                continue
            if expected_cidr and (
                _canonical_cidr(node_port.get("cidr")) != expected_cidr
                or _canonical_cidr(segment_port.get("cidr")) != expected_cidr
            ):
                continue
            if ip is not None and str(node_port.get("ip") or "").strip() != str(ip):
                continue
            return []

        return [
            _fact_issue(
                fact_kind,
                "addressing_mismatch",
                f"{node} interface to {segment} must match requested addressing",
                targets=[node, segment],
                details={
                    "expected_edge": [node, segment],
                    "expected_cidr": expected_cidr or None,
                    "expected_ip": ip,
                    "actual_links": [_link_addressing(self, link) for link in links],
                },
            )
        ]

    def check_direct_link(self, node_a: str, node_b: str, *, link_key: str | None = None) -> list[dict[str, Any]]:
        return _check_edges(self, "logical.topology.direct", [(node_a, node_b)], link_keys=[link_key] if link_key else None)

    def check_chain(self, nodes: list[str], *, link_keys: list[str | None] | None = None) -> list[dict[str, Any]]:
        edges = list(zip(nodes, nodes[1:]))
        return _check_edges(self, "logical.topology.chain", edges, link_keys=link_keys)

    def check_ring(self, nodes: list[str], *, link_keys: list[str | None] | None = None) -> list[dict[str, Any]]:
        if len(nodes) < 3:
            return [
                _fact_issue(
                    "logical.topology.ring",
                    "too_few_nodes",
                    "ring topology requires at least three nodes",
                    targets=list(nodes),
                    details={"expected_node_count_min": 3, "actual_node_count": len(nodes)},
                )
            ]
        edges = list(zip(nodes, [*nodes[1:], nodes[0]]))
        return _check_edges(self, "logical.topology.ring", edges, link_keys=link_keys)

    def check_star(self, *, center: str, leaves: list[str], link_keys: list[str | None] | None = None) -> list[dict[str, Any]]:
        edges = [(center, leaf) for leaf in leaves]
        return _check_edges(self, "logical.topology.star", edges, link_keys=link_keys)

    def check_mesh(self, nodes: list[str]) -> list[dict[str, Any]]:
        edges = [
            (left, right)
            for index, left in enumerate(nodes)
            for right in nodes[index + 1 :]
        ]
        return _check_edges(self, "logical.topology.mesh", edges)

    def check_image_exact(self, node: str, image_id: str) -> list[dict[str, Any]]:
        fact_kind = "physical.image.exact"
        payload = self.node(node)
        if payload is None:
            return [
                _fact_issue(
                    fact_kind,
                    "missing_node",
                    f"{node} must exist to check image",
                    targets=[node],
                    details={"expected_image_id": image_id},
                )
            ]
        actual = _node_image_id(payload)
        if actual == image_id:
            return []
        suffix = "missing" if actual is None else "mismatch"
        return [
            _fact_issue(
                fact_kind,
                suffix,
                f"{node} image must be {image_id}",
                targets=[node],
                details={"expected_image_id": image_id, "actual_image_id": actual},
            )
        ]

    def check_flavor_minimum(self, node: str, *, vcpu: int, ram: int, disk: int) -> list[dict[str, Any]]:
        fact_kind = "physical.flavor.minimum"
        expected = {"vcpu": vcpu, "ram": ram, "disk": disk}
        payload = self.node(node)
        if payload is None:
            return [
                _fact_issue(
                    fact_kind,
                    "missing_node",
                    f"{node} must exist to check flavor",
                    targets=[node],
                    details={"expected_minimum": expected},
                )
            ]
        actual = _node_flavor(payload)
        if actual is None:
            return [
                _fact_issue(
                    fact_kind,
                    "missing",
                    f"{node} must define a flavor",
                    targets=[node],
                    details={"expected_minimum": expected, "actual_flavor": None},
                )
            ]
        too_small = {key: {"expected": expected[key], "actual": actual.get(key)} for key in expected if int(actual.get(key) or 0) < expected[key]}
        if not too_small:
            return []
        return [
            _fact_issue(
                fact_kind,
                "too_small",
                f"{node} flavor is below minimum requirements",
                targets=[node],
                details={"expected_minimum": expected, "actual_flavor": actual, "too_small": too_small},
            )
        ]

    def check_flavor_exact(self, node: str, *, vcpu: int, ram: int, disk: int) -> list[dict[str, Any]]:
        fact_kind = "physical.flavor.exact"
        expected = {"vcpu": vcpu, "ram": ram, "disk": disk}
        payload = self.node(node)
        if payload is None:
            return [
                _fact_issue(
                    fact_kind,
                    "missing_node",
                    f"{node} must exist to check flavor",
                    targets=[node],
                    details={"expected_flavor": expected},
                )
            ]
        actual = _node_flavor(payload)
        if actual is None:
            return [
                _fact_issue(
                    fact_kind,
                    "missing",
                    f"{node} must define a flavor",
                    targets=[node],
                    details={"expected_flavor": expected, "actual_flavor": None},
                )
            ]
        if actual == expected:
            return []
        return [
            _fact_issue(
                fact_kind,
                "mismatch",
                f"{node} flavor must match requested values",
                targets=[node],
                details={"expected_flavor": expected, "actual_flavor": actual},
            )
        ]

    def _build_adjacency(self) -> dict[str, set[str]]:
        adjacency: dict[str, set[str]] = {node_id: set() for node_id in self._nodes_by_id}
        for payload in self._links_by_id.values():
            node_a = str(payload.get("from_node") or "")
            node_b = str(payload.get("to_node") or "")
            if not node_a or not node_b or node_a == node_b:
                continue
            adjacency.setdefault(node_a, set()).add(node_b)
            adjacency.setdefault(node_b, set()).add(node_a)
        return adjacency


def _link_has_endpoint(payload: dict[str, Any], *, node_id: str | None, port_id: str) -> bool:
    if node_id is not None:
        return (
            (payload.get("from_node") == node_id and payload.get("from_port") == port_id)
            or (payload.get("to_node") == node_id and payload.get("to_port") == port_id)
        )
    return port_id in {payload.get("from_port"), payload.get("to_port")}


def _link_matches_key(payload: dict[str, Any], link_key: str) -> bool:
    return str(payload.get("id") or "").endswith(f"-{link_key}")


def _fact_issue(
    fact_kind: str,
    suffix: str,
    message: str,
    *,
    targets: list[str],
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return issue(
        f"{fact_kind}.{suffix}",
        message,
        targets=targets,
        fact_kind=fact_kind,
        repair_target="graph",
        details=details,
    )


def _check_edges(
    view: TGraphView,
    fact_kind: str,
    edges: list[tuple[str, str]],
    *,
    link_keys: list[str | None] | None = None,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for index, (node_a, node_b) in enumerate(edges):
        link_key = link_keys[index] if link_keys is not None and index < len(link_keys) else None
        if view.links(between=[node_a, node_b], link_key=link_key):
            continue
        issues.append(
            _fact_issue(
                fact_kind,
                "missing_edge",
                f"{node_a} must connect directly to {node_b}",
                targets=[node_a, node_b],
                details={"expected_edge": [node_a, node_b], "expected_link_key": link_key},
            )
        )
    return issues


def _endpoint_port(view: TGraphView, link: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    if link.get("from_node") == node_id:
        return view.port(node_id, str(link.get("from_port") or ""))
    if link.get("to_node") == node_id:
        return view.port(node_id, str(link.get("to_port") or ""))
    return None


def _link_addressing(view: TGraphView, link: dict[str, Any]) -> dict[str, Any]:
    from_node = str(link.get("from_node") or "")
    to_node = str(link.get("to_node") or "")
    from_port = _endpoint_port(view, link, from_node) if from_node else None
    to_port = _endpoint_port(view, link, to_node) if to_node else None
    return {
        "link": link.get("id"),
        "from": {"node": from_node, "port": link.get("from_port"), "ip": (from_port or {}).get("ip"), "cidr": (from_port or {}).get("cidr")},
        "to": {"node": to_node, "port": link.get("to_port"), "ip": (to_port or {}).get("ip"), "cidr": (to_port or {}).get("cidr")},
    }


def _node_image_id(node: dict[str, Any]) -> str | None:
    image = node.get("image")
    if not isinstance(image, dict):
        return None
    image_id = image.get("id")
    return str(image_id) if image_id else None


def _node_flavor(node: dict[str, Any]) -> dict[str, int] | None:
    flavor = node.get("flavor")
    if not isinstance(flavor, dict):
        return None
    return {
        "vcpu": int(flavor.get("vcpu") or 0),
        "ram": int(flavor.get("ram") or 0),
        "disk": int(flavor.get("disk") or 0),
    }


def _canonical_cidr(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return str(ipaddress.ip_network(text, strict=False))
    except ValueError:
        return text
