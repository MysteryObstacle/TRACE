from __future__ import annotations

from typing import Any

from trace.tools.tgraph.model import TGraphJSON, ensure_tgraph_json


class TGraphRuntime:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    @classmethod
    def from_json(cls, payload: TGraphJSON | dict[str, Any]) -> "TGraphRuntime":
        graph = ensure_tgraph_json(payload).model_dump(mode="json")
        port_owner: dict[str, str] = {}
        for node in graph.get("nodes", []):
            for port in node.get("ports", []):
                port_owner[port["id"]] = node["id"]

        normalized_links: list[dict[str, Any]] = []
        for link in graph.get("links", []):
            item = dict(link)
            endpoint_a, endpoint_b = sorted((item["from_port"], item["to_port"]))
            item["from_port"] = endpoint_a
            item["to_port"] = endpoint_b
            item["id"] = f"{endpoint_a}--{endpoint_b}"
            item["from_node"] = port_owner.get(endpoint_a)
            item["to_node"] = port_owner.get(endpoint_b)
            normalized_links.append(item)

        graph["links"] = normalized_links
        return cls(TGraphJSON.model_validate(graph).model_dump(mode="json"))

    def to_json(self) -> dict[str, Any]:
        return TGraphJSON.model_validate(self._payload).model_dump(mode="json")

    def get_graph_summary(self) -> dict[str, int | str]:
        payload = self.to_json()
        return {
            "profile": payload["profile"],
            "node_count": len(payload["nodes"]),
            "link_count": len(payload["links"]),
        }

    def topology_view(self) -> dict[str, list[str]]:
        payload = self.to_json()
        return {
            "nodes": sorted(node["id"] for node in payload["nodes"]),
            "links": sorted(link["id"] for link in payload["links"]),
        }

    def get_node(self, node_id: str) -> dict[str, Any]:
        for node in self.to_json()["nodes"]:
            if node["id"] == node_id:
                return node
        raise KeyError(f"unknown node id: {node_id}")

    def get_nodes(self, node_ids: list[str] | None = None) -> list[dict[str, Any]]:
        nodes = self.to_json()["nodes"]
        if node_ids is None:
            return nodes
        node_map = {node["id"]: node for node in nodes}
        result: list[dict[str, Any]] = []
        for node_id in node_ids:
            key = str(node_id)
            if key not in node_map:
                raise KeyError(f"unknown node id: {key}")
            result.append(node_map[key])
        return result

    def get_link(self, link_id: str) -> dict[str, Any]:
        for link in self.to_json()["links"]:
            if link["id"] == link_id:
                return link
        raise KeyError(f"unknown link id: {link_id}")

    def get_links(
        self,
        link_ids: list[str] | None = None,
        *,
        node_id: str | None = None,
        port_id: str | None = None,
    ) -> list[dict[str, Any]]:
        links = self.to_json()["links"]
        if link_ids is not None:
            link_map = {link["id"]: link for link in links}
            result: list[dict[str, Any]] = []
            for link_id in link_ids:
                key = str(link_id)
                if key not in link_map:
                    raise KeyError(f"unknown link id: {key}")
                result.append(link_map[key])
            return result
        selected: list[dict[str, Any]] = []
        for link in links:
            if node_id is not None and node_id not in {link.get("from_node"), link.get("to_node")}:
                continue
            if port_id is not None and port_id not in {link.get("from_port"), link.get("to_port")}:
                continue
            selected.append(link)
        return selected

    def validate(self) -> dict[str, Any]:
        from trace.tools.tgraph.validate import run_default_validators

        return run_default_validators(self.to_json()).model_dump(mode="json")

    def list_nodes(self) -> list[str]:
        return [node["id"] for node in self.to_json()["nodes"]]

    def neighbors(self, node_id: str) -> list[str]:
        neighbors: set[str] = set()
        for link in self.to_json()["links"]:
            if link.get("from_node") == node_id and link.get("to_node"):
                neighbors.add(link["to_node"])
            elif link.get("to_node") == node_id and link.get("from_node"):
                neighbors.add(link["from_node"])
        return sorted(neighbors)

    def begin_transaction(self):
        from trace.tools.tgraph.transaction import TGraphTransaction

        return TGraphTransaction(self)

    def add_node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        *,
        image: dict[str, Any] | None = None,
        flavor: dict[str, Any] | None = None,
        levels: list[str] | None = None,
    ) -> dict[str, Any]:
        try:
            tx = self.begin_transaction()
            tx.add_node(node_id, node_type, label, image=image, flavor=flavor)
            return tx.commit(levels=levels)
        except (KeyError, ValueError) as exc:
            return _runtime_error_result(exc)

    def update_node(self, node_id: str, *, levels: list[str] | None = None, **attrs: Any) -> dict[str, Any]:
        try:
            tx = self.begin_transaction()
            tx.update_node(node_id, **attrs)
            return tx.commit(levels=levels)
        except (KeyError, ValueError) as exc:
            return _runtime_error_result(exc)

    def add_link(
        self,
        from_port: str,
        to_port: str,
        *,
        from_node: str | None = None,
        to_node: str | None = None,
        from_ip: str = "",
        from_cidr: str = "",
        to_ip: str = "",
        to_cidr: str = "",
        levels: list[str] | None = None,
    ) -> dict[str, Any]:
        try:
            tx = self.begin_transaction()
            tx.add_link(
                from_port,
                to_port,
                from_node=from_node,
                to_node=to_node,
                from_ip=from_ip,
                from_cidr=from_cidr,
                to_ip=to_ip,
                to_cidr=to_cidr,
            )
            return tx.commit(levels=levels)
        except (KeyError, ValueError) as exc:
            return _runtime_error_result(exc)

    def update_link(
        self,
        link_id: str,
        *,
        from_port: str,
        to_port: str,
        from_node: str | None = None,
        to_node: str | None = None,
        from_ip: str = "",
        from_cidr: str = "",
        to_ip: str = "",
        to_cidr: str = "",
        levels: list[str] | None = None,
    ) -> dict[str, Any]:
        try:
            tx = self.begin_transaction()
            tx.update_link(
                link_id,
                from_port=from_port,
                to_port=to_port,
                from_node=from_node,
                to_node=to_node,
                from_ip=from_ip,
                from_cidr=from_cidr,
                to_ip=to_ip,
                to_cidr=to_cidr,
            )
            return tx.commit(levels=levels)
        except (KeyError, ValueError) as exc:
            return _runtime_error_result(exc)

    def remove_link(self, link_id: str, *, levels: list[str] | None = None) -> dict[str, Any]:
        try:
            tx = self.begin_transaction()
            tx.remove_link(link_id)
            return tx.commit(levels=levels)
        except (KeyError, ValueError) as exc:
            return _runtime_error_result(exc)

    def remove_node(self, node_id: str, *, cascade: bool = True, levels: list[str] | None = None) -> dict[str, Any]:
        try:
            tx = self.begin_transaction()
            tx.remove_node(node_id, cascade=cascade)
            return tx.commit(levels=levels)
        except (KeyError, ValueError) as exc:
            return _runtime_error_result(exc)


def _runtime_error_result(exc: Exception) -> dict[str, Any]:
    return {
        "ok": False,
        "issues": [
            {
                "code": "runtime_error",
                "message": str(exc),
                "severity": "error",
                "targets": [],
                "json_paths": [],
                "provenance": {"layer": "f1", "source": "builtin"},
            }
        ],
        "change_map": {},
    }
