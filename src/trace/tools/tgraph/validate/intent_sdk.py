from __future__ import annotations

import ipaddress
from collections import deque
from typing import Any, Callable

from trace.tools.tgraph.runtime import TGraphRuntime
from trace.tools.tgraph.validate.issues import issue


def connect_nodes(tgraph: "IntentTGraphView", *, node_a: str, node_b: str) -> list[dict[str, Any]]:
    node_a = str(node_a or "").strip()
    node_b = str(node_b or "").strip()
    if not node_a or not node_b:
        return [issue("checkpoint_param_missing", "connect_nodes requires node_a and node_b")]
    if tgraph.get_node(node_a) is None or tgraph.get_node(node_b) is None:
        return [issue("checkpoint_target_missing", f"unknown node in connect_nodes: {node_a}, {node_b}")]
    if node_b in tgraph.neighbors(node_a):
        return []
    return [issue("missing_required_link", f"{node_a} is not directly connected to {node_b}", targets=[node_a, node_b])]


def _canonical_cidr(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return str(ipaddress.ip_network(text, strict=False))
    except ValueError:
        return text


def _port_by_id(node: dict[str, Any], port_id: str) -> dict[str, Any] | None:
    for port in node.get("ports", []) or []:
        if str(port.get("id") or "") == port_id:
            return port
    return None


def switch_has_subnet(tgraph: "IntentTGraphView", *, switch_id: str, expected_cidr: str) -> list[dict[str, Any]]:
    switch_id = str(switch_id or "").strip()
    expected_cidr = str(expected_cidr or "").strip()
    if not switch_id or not expected_cidr:
        return [issue("checkpoint_param_missing", "switch_has_subnet requires switch_id and expected_cidr")]

    node = tgraph.get_node(switch_id)
    if node is None:
        return [issue("checkpoint_target_missing", f"unknown switch in switch_has_subnet: {switch_id}", targets=[switch_id])]
    if str(node.get("type") or "") != "switch":
        return [issue("checkpoint_target_type_mismatch", f"{switch_id} is not a switch", targets=[switch_id])]

    ports = node.get("ports", []) or []
    if not ports:
        return [issue("switch_subnet_missing", f"{switch_id} has no ports for subnet {expected_cidr}", targets=[switch_id])]

    expected = _canonical_cidr(expected_cidr)
    mismatched: list[str] = []
    for port in ports:
        port_id = str(port.get("id") or "unknown")
        if str(port.get("ip") or "").strip():
            mismatched.append(port_id)
            continue
        if _canonical_cidr(port.get("cidr")) != expected:
            mismatched.append(port_id)

    if mismatched:
        return [
            issue(
                "switch_subnet_mismatch",
                f"{switch_id} ports do not all represent subnet {expected_cidr}: {mismatched}",
                targets=[switch_id, *mismatched],
            )
        ]
    return []


def node_interface_on_segment(
    tgraph: "IntentTGraphView",
    *,
    node_id: str,
    segment_id: str,
    expected_ip: str,
    expected_cidr: str,
) -> list[dict[str, Any]]:
    node_id = str(node_id or "").strip()
    segment_id = str(segment_id or "").strip()
    expected_ip = str(expected_ip or "").strip()
    expected_cidr = str(expected_cidr or "").strip()
    if not node_id or not segment_id or not expected_ip or not expected_cidr:
        return [
            issue(
                "checkpoint_param_missing",
                "node_interface_on_segment requires node_id, segment_id, expected_ip, and expected_cidr",
            )
        ]

    node = tgraph.get_node(node_id)
    segment = tgraph.get_node(segment_id)
    if node is None or segment is None:
        return [
            issue(
                "checkpoint_target_missing",
                f"unknown node or segment in node_interface_on_segment: {node_id}, {segment_id}",
                targets=[node_id, segment_id],
            )
        ]
    if str(segment.get("type") or "") != "switch":
        return [issue("checkpoint_target_type_mismatch", f"{segment_id} is not a switch segment", targets=[segment_id])]

    expected = _canonical_cidr(expected_cidr)
    has_segment_link = False
    for link in tgraph.list_links(node_id=node_id):
        if link.get("peer_node") != segment_id:
            continue
        has_segment_link = True
        raw_port_id = link.get("from_port") if link.get("from_node") == node_id else link.get("to_port")
        port_id = str(raw_port_id or "")
        port = _port_by_id(node, port_id)
        if port is None:
            continue
        if str(port.get("ip") or "").strip() == expected_ip and _canonical_cidr(port.get("cidr")) == expected:
            return []

    if not has_segment_link:
        return [issue("interface_segment_attachment_missing", f"{node_id} is not attached to segment {segment_id}", targets=[node_id, segment_id])]
    return [
        issue(
            "interface_ip_or_cidr_mismatch",
            f"{node_id} interface on {segment_id} does not use {expected_ip}/{expected_cidr.split('/')[-1]}",
            targets=[node_id, segment_id],
        )
    ]


def path_exists(tgraph: "IntentTGraphView", *, source_id: str, target_id: str) -> list[dict[str, Any]]:
    source_id = str(source_id or "").strip()
    target_id = str(target_id or "").strip()
    if not source_id or not target_id:
        return [issue("checkpoint_param_missing", "path_exists requires source_id and target_id")]
    if tgraph.check_reachability(source_id, target_id):
        return []
    return [issue("missing_required_path", f"no path from {source_id} to {target_id}", targets=[source_id, target_id])]


def path_must_include(
    tgraph: "IntentTGraphView",
    *,
    source_id: str,
    target_id: str,
    via: str,
) -> list[dict[str, Any]]:
    source_id = str(source_id or "").strip()
    target_id = str(target_id or "").strip()
    via = str(via or "").strip()
    if not source_id or not target_id or not via:
        return [issue("checkpoint_param_missing", "path_must_include requires source_id, target_id, and via")]
    if tgraph.is_reachable(source_id, target_id, via=via):
        return []
    return [issue("required_path_via_missing", f"no path from {source_id} to {target_id} via {via}", targets=[source_id, target_id, via])]

SDK_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "connect_nodes": connect_nodes,
    "switch_has_subnet": switch_has_subnet,
    "node_interface_on_segment": node_interface_on_segment,
    "path_exists": path_exists,
    "path_must_include": path_must_include,
}


SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "Exception": Exception,
    "float": float,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
}


SDK_GLOBALS: dict[str, Any] = {
    **SDK_FUNCTIONS,
    "issue": issue,
    "ipaddress": ipaddress,
}


class IntentTGraphView:
    def __init__(self, graph_json: dict[str, Any]) -> None:
        self._graph = graph_json
        self.nodes = list(graph_json.get("nodes", []))
        self._node_map = {str(node.get("id") or ""): node for node in self.nodes}
        self._port_owner: dict[str, str] = {}
        for node in self.nodes:
            node_id = str(node.get("id") or "")
            for port in node.get("ports", []) or []:
                port_id = str(port.get("id") or "")
                if port_id:
                    self._port_owner[port_id] = node_id
        self.links = [self._enrich_link(link) for link in graph_json.get("links", [])]
        self._link_map = {str(link.get("id") or ""): link for link in self.links}
        self._adj = self._build_adjacency()

    @classmethod
    def from_json(cls, graph_json: dict[str, Any]) -> "IntentTGraphView":
        return cls(TGraphRuntime.from_json(graph_json).to_json())

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        return self._node_map.get(node_id)

    def get_nodes(self, node_ids: list[str] | None = None) -> list[dict[str, Any]]:
        if node_ids is None:
            return [dict(node) for node in self.nodes]
        selected: list[dict[str, Any]] = []
        for node_id in node_ids:
            node = self.get_node(str(node_id))
            if node is not None:
                selected.append(dict(node))
        return selected

    def get_link(self, link_id: str) -> dict[str, Any] | None:
        link = self._link_map.get(link_id)
        if link is None:
            return None
        return dict(link)

    def list_links(self, node_id: str | None = None, port_id: str | None = None) -> list[dict[str, Any]]:
        if node_id is None and port_id is None:
            return [dict(link) for link in self.links]
        selected: list[dict[str, Any]] = []
        for link in self.links:
            from_port = str(link.get("from_port") or "")
            to_port = str(link.get("to_port") or "")
            from_node = str(link.get("from_node") or self._port_owner.get(from_port) or "")
            to_node = str(link.get("to_node") or self._port_owner.get(to_port) or "")
            if port_id and port_id not in {from_port, to_port}:
                continue
            if node_id and node_id not in {from_node, to_node}:
                continue
            relative_node_id = node_id
            if relative_node_id is None and port_id:
                if port_id == from_port:
                    relative_node_id = from_node
                elif port_id == to_port:
                    relative_node_id = to_node
            selected.append(self._present_link(link, relative_node_id=relative_node_id))
        return selected

    def get_links(
        self,
        link_ids: list[str] | str | None = None,
        *,
        node_id: str | None = None,
        port_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if isinstance(link_ids, str) and node_id is None and port_id is None:
            return self.list_links(node_id=link_ids)
        if link_ids is not None:
            requested = [str(item) for item in link_ids]
            selected: list[dict[str, Any]] = []
            for link_id in requested:
                link = self.get_link(link_id)
                if link is not None:
                    selected.append(link)
            return selected
        return self.list_links(node_id=node_id, port_id=port_id)

    def get_links_for_node(self, node_id: str) -> list[dict[str, Any]]:
        return self.list_links(node_id=node_id)

    def neighbors(self, node_id: str) -> list[str]:
        return sorted(self._adj.get(node_id, set()))

    def check_reachability(self, source_id: str, target_id: str) -> bool:
        if source_id not in self._adj or target_id not in self._adj:
            return False
        if source_id == target_id:
            return True
        visited = {source_id}
        queue = deque([source_id])
        while queue:
            current = queue.popleft()
            for nxt in self._adj.get(current, set()):
                if nxt == target_id:
                    return True
                if nxt in visited:
                    continue
                visited.add(nxt)
                queue.append(nxt)
        return False

    def find_path(self, source_id: str, target_ids: str | list[str]) -> list[str] | None:
        targets = {target_ids} if isinstance(target_ids, str) else {str(item) for item in target_ids}
        if not targets or source_id not in self._adj:
            return None
        queue = deque([[source_id]])
        visited = {source_id}
        while queue:
            path = queue.popleft()
            current = path[-1]
            if current in targets:
                return path
            for nxt in self._adj.get(current, set()):
                if nxt in visited:
                    continue
                visited.add(nxt)
                queue.append([*path, nxt])
        return None

    def find_paths(self, source_id: str, target_id: str, cutoff: int | None = None) -> list[list[str]]:
        if source_id not in self._adj or target_id not in self._adj:
            return []
        if cutoff is None:
            cutoff = max(len(self._adj) - 1, 1)
        paths: list[list[str]] = []

        def dfs(current: str, path: list[str]) -> None:
            if len(path) - 1 > cutoff:
                return
            if current == target_id:
                paths.append(path[:])
                return
            for nxt in self._adj.get(current, set()):
                if nxt in path:
                    continue
                path.append(nxt)
                dfs(nxt, path)
                path.pop()

        dfs(source_id, [source_id])
        return paths

    def is_reachable(self, source_id: str, target_id: str, via: str | None = None) -> bool:
        if via is None:
            return self.check_reachability(source_id, target_id)
        for path in self.find_paths(source_id, target_id):
            if via in path:
                return True
        return False

    def _build_adjacency(self) -> dict[str, set[str]]:
        adjacency = {node_id: set() for node_id in self._node_map}
        for link in self.links:
            from_port = str(link.get("from_port") or "")
            to_port = str(link.get("to_port") or "")
            node_a = str(link.get("from_node") or self._port_owner.get(from_port) or "")
            node_b = str(link.get("to_node") or self._port_owner.get(to_port) or "")
            if not node_a or not node_b or node_a == node_b:
                continue
            adjacency.setdefault(node_a, set()).add(node_b)
            adjacency.setdefault(node_b, set()).add(node_a)
        return adjacency

    def _enrich_link(self, link: dict[str, Any]) -> dict[str, Any]:
        data = dict(link)
        from_port = str(data.get("from_port") or "")
        to_port = str(data.get("to_port") or "")
        from_node = str(data.get("from_node") or self._port_owner.get(from_port) or "")
        to_node = str(data.get("to_node") or self._port_owner.get(to_port) or "")
        data["from_node"] = from_node
        data["to_node"] = to_node
        return data

    def _present_link(self, link: dict[str, Any], *, relative_node_id: str | None = None) -> dict[str, Any]:
        data = dict(link)
        if not relative_node_id:
            return data

        from_node = str(data.get("from_node") or "")
        to_node = str(data.get("to_node") or "")
        from_port = str(data.get("from_port") or "")
        to_port = str(data.get("to_port") or "")
        if relative_node_id == from_node:
            data["peer_node"] = to_node
            data["peer_port"] = to_port
        elif relative_node_id == to_node:
            data["peer_node"] = from_node
            data["peer_port"] = from_port
        return data
