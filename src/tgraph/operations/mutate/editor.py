from __future__ import annotations

import copy
import re
from typing import Any

from tgraph.core.graph import TGraph

_LINK_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")


class TGraphEditor:
    def __init__(self, graph: TGraph | dict[str, Any]) -> None:
        current = graph if isinstance(graph, TGraph) else TGraph.model_validate(graph)
        self._graph = current.model_dump(mode="json")
        self.operations: list[dict[str, Any]] = []

    def to_graph(self) -> TGraph:
        data = copy.deepcopy(self._graph)
        for node in data.get("nodes", []):
            node["ports"] = sorted(node.get("ports", []), key=lambda item: item["id"])
        data["links"] = sorted(data.get("links", []), key=lambda item: item["id"])
        return TGraph.model_validate(data)

    def ensure_node(self, node_id: str, *, type: str = "computer", label: str | None = None) -> dict[str, Any]:
        node = self._find_node(node_id)
        if node is None:
            node = {"id": node_id, "type": type, "label": label or node_id, "ports": []}
            self._graph.setdefault("nodes", []).append(node)
            self.operations.append({"op": "ensure_node", "node": node_id})
        return node

    def ensure_direct_link(self, node_a: str, node_b: str, *, link_key: str | None = None) -> dict[str, Any]:
        key = self._normalize_link_key(link_key)
        link_id = _link_id(node_a, node_b, key)
        existing = self._find_link(link_id)
        if existing is not None:
            return existing

        self._require_node(node_a)
        self._require_node(node_b)
        port_a = self._new_port(node_a, node_b)
        port_b = self._new_port(node_b, node_a)
        link = {
            "id": link_id,
            "from_node": node_a,
            "from_port": port_a["id"],
            "to_node": node_b,
            "to_port": port_b["id"],
        }
        self._graph.setdefault("links", []).append(link)
        self.operations.append({"op": "ensure_direct_link", "link": link_id, "nodes": [node_a, node_b], "link_key": key})
        return link

    def ensure_chain(self, nodes: list[str], *, link_keys: list[str | None] | None = None) -> None:
        for index, (node_a, node_b) in enumerate(zip(nodes, nodes[1:])):
            self.ensure_direct_link(node_a, node_b, link_key=_link_key_at(link_keys, index))

    def ensure_ring(self, nodes: list[str], *, link_keys: list[str | None] | None = None) -> None:
        if len(nodes) < 3:
            raise ValueError("ring requires at least three nodes")
        for index, (node_a, node_b) in enumerate(zip(nodes, [*nodes[1:], nodes[0]])):
            self.ensure_direct_link(node_a, node_b, link_key=_link_key_at(link_keys, index))

    def ensure_star(self, *, center: str, leaves: list[str], link_keys: list[str | None] | None = None) -> None:
        for index, leaf in enumerate(leaves):
            self.ensure_direct_link(center, leaf, link_key=_link_key_at(link_keys, index))

    def ensure_mesh(self, nodes: list[str]) -> None:
        for index, node_a in enumerate(nodes):
            for node_b in nodes[index + 1 :]:
                self.ensure_direct_link(node_a, node_b)

    def ensure_subnet(self, switch: str, *, cidr: str) -> None:
        node = self._require_node(switch)
        for port in node.setdefault("ports", []):
            if port.get("cidr") != cidr:
                port["cidr"] = cidr
        self.operations.append({"op": "ensure_subnet", "node": switch, "cidr": cidr})

    def ensure_interface(self, node: str, *, segment: str, cidr: str, ip: str | None = None, link_key: str | None = None) -> dict[str, Any]:
        link = self.ensure_direct_link(node, segment, link_key=link_key)
        node_port = self._endpoint_port(link, node)
        segment_port = self._endpoint_port(link, segment)
        if node_port is not None:
            node_port["cidr"] = cidr
            if ip is not None:
                node_port["ip"] = ip
        if segment_port is not None:
            segment_port["cidr"] = cidr
        self.operations.append({"op": "ensure_interface", "node": node, "segment": segment, "cidr": cidr, "ip": ip})
        return link

    def set_image(self, node: str, image_id: str, *, name: str | None = None) -> None:
        payload = self._require_node(node)
        payload["image"] = {"id": image_id, "name": name or image_id}
        self.operations.append({"op": "set_image", "node": node, "image_id": image_id})

    def set_flavor(self, node: str, *, vcpu: int, ram: int, disk: int) -> None:
        payload = self._require_node(node)
        payload["flavor"] = {"vcpu": vcpu, "ram": ram, "disk": disk}
        self.operations.append({"op": "set_flavor", "node": node, "flavor": dict(payload["flavor"])})

    def remove_direct_link(self, node_a: str, node_b: str, *, link_key: str | None = None) -> dict[str, Any]:
        key = self._normalize_link_key(link_key)
        link_id = _link_id(node_a, node_b, key)
        links = [link for link in self._graph.get("links", []) if link.get("id") == link_id]
        return self._remove_links(links, destructive=False)

    def remove_links_between(self, node_a: str, node_b: str) -> dict[str, Any]:
        pair = tuple(sorted((node_a, node_b)))
        links = [
            link
            for link in self._graph.get("links", [])
            if tuple(sorted((str(link.get("from_node")), str(link.get("to_node"))))) == pair
        ]
        return self._remove_links(links, destructive=True)

    def remove_node(self, node: str, *, cascade: bool = True) -> dict[str, Any]:
        self._require_node(node)
        incident = [
            link
            for link in self._graph.get("links", [])
            if node in {link.get("from_node"), link.get("to_node")}
        ]
        if incident and not cascade:
            raise ValueError(f"node has incident links: {node}")
        removed = self._remove_links(incident, destructive=cascade)
        self._graph["nodes"] = [item for item in self._graph.get("nodes", []) if item.get("id") != node]
        removed["nodes_removed"] = [node]
        self.operations.append({"op": "remove_node", "node": node, "cascade": cascade})
        return removed

    def _remove_links(self, links: list[dict[str, Any]], *, destructive: bool) -> dict[str, Any]:
        links_removed = sorted(str(link["id"]) for link in links)
        ports_removed: list[str] = []
        for link in links:
            self._graph["links"] = [item for item in self._graph.get("links", []) if item is not link]
            for endpoint_node, endpoint_port in (
                (str(link["from_node"]), str(link["from_port"])),
                (str(link["to_node"]), str(link["to_port"])),
            ):
                if self._port_is_incident(endpoint_node, endpoint_port):
                    continue
                node = self._require_node(endpoint_node)
                node["ports"] = [port for port in node.get("ports", []) if port.get("id") != endpoint_port]
                ports_removed.append(f"{endpoint_node}.{endpoint_port}")
        result = {"links_removed": links_removed, "ports_removed": sorted(ports_removed), "destructive": destructive}
        if links_removed:
            self.operations.append({"op": "remove_links", **result})
        return result

    def _new_port(self, node_id: str, peer_id: str) -> dict[str, Any]:
        node = self._require_node(node_id)
        port_id = self._next_port_id(node, peer_id)
        port = {"id": port_id, "ip": "", "cidr": ""}
        node.setdefault("ports", []).append(port)
        return port

    def _next_port_id(self, node: dict[str, Any], peer_id: str) -> str:
        prefix = f"_{peer_id}-"
        used = []
        for port in node.get("ports", []):
            port_id = str(port.get("id") or "")
            if port_id.startswith(prefix):
                suffix = port_id.removeprefix(prefix)
                if suffix.isdigit():
                    used.append(int(suffix))
        return f"{prefix}{max(used, default=0) + 1}"

    def _endpoint_port(self, link: dict[str, Any], node_id: str) -> dict[str, Any] | None:
        if link.get("from_node") == node_id:
            return self._find_port(node_id, str(link.get("from_port")))
        if link.get("to_node") == node_id:
            return self._find_port(node_id, str(link.get("to_port")))
        return None

    def _port_is_incident(self, node_id: str, port_id: str) -> bool:
        for link in self._graph.get("links", []):
            if (link.get("from_node"), link.get("from_port")) == (node_id, port_id):
                return True
            if (link.get("to_node"), link.get("to_port")) == (node_id, port_id):
                return True
        return False

    def _find_node(self, node_id: str) -> dict[str, Any] | None:
        for node in self._graph.get("nodes", []):
            if node.get("id") == node_id:
                return node
        return None

    def _require_node(self, node_id: str) -> dict[str, Any]:
        node = self._find_node(node_id)
        if node is None:
            raise ValueError(f"unknown node id: {node_id}")
        return node

    def _find_port(self, node_id: str, port_id: str) -> dict[str, Any] | None:
        node = self._find_node(node_id)
        if node is None:
            return None
        for port in node.get("ports", []):
            if port.get("id") == port_id:
                return port
        return None

    def _find_link(self, link_id: str) -> dict[str, Any] | None:
        for link in self._graph.get("links", []):
            if link.get("id") == link_id:
                return link
        return None

    def _normalize_link_key(self, link_key: str | None) -> str:
        key = str(link_key or "1")
        if not _LINK_KEY_RE.match(key):
            raise ValueError("link_key must match ^[A-Za-z0-9_]+$ and must not contain '-'")
        return key


def _link_id(node_a: str, node_b: str, key: str) -> str:
    left, right = sorted((node_a, node_b))
    return f"{left}-{right}-{key}"


def _link_key_at(link_keys: list[str | None] | None, index: int) -> str | None:
    if link_keys is None or index >= len(link_keys):
        return None
    return link_keys[index]
