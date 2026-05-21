from __future__ import annotations

from typing import Any

from trace.tools.tgraph.validate import run_default_validators
from trace.tools.tgraph.validate.f1_format import f1_format
from trace.tools.tgraph.validate.f2_schema import f2_schema
from trace.tools.tgraph.validate.f3_consistency import f3_consistency
from trace.tools.tgraph.validate.f4_intent import f4_intent
from trace.tools.tgraph.validate.types import ValidationIssue, ValidationReport


class TGraphTransaction:
    def __init__(self, runtime) -> None:
        self._runtime = runtime
        self._working = runtime.to_json()

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
    ) -> None:
        """Materialize or update port endpoints only as part of wiring this link.

        If an undirected link between the two ports already exists, no second link row is added;
        endpoint addressing is still updated when IP/CIDR values are provided.
        """
        self._ensure_endpoint(
            port_id=from_port,
            node_id=from_node,
            ip=from_ip,
            cidr=from_cidr,
        )
        self._ensure_endpoint(
            port_id=to_port,
            node_id=to_node,
            ip=to_ip,
            cidr=to_cidr,
        )
        if self._has_link_between(from_port, to_port):
            return
        self._working.setdefault("links", []).append(
            {
                "id": f"{from_port}--{to_port}",
                "from_port": from_port,
                "to_port": to_port,
            }
        )

    def add_node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        *,
        image: dict[str, Any] | None = None,
        flavor: dict[str, Any] | None = None,
    ) -> None:
        if self._find_node(node_id) is not None:
            raise KeyError(f"node id already exists: {node_id}")
        self._working.setdefault("nodes", []).append(
            {
                "id": node_id,
                "type": node_type,
                "label": label,
                "ports": [],
                "image": image,
                "flavor": flavor,
            }
        )

    def update_node(self, node_id: str, **attrs: Any) -> None:
        node = self._find_node(node_id)
        if node is None:
            raise KeyError(f"unknown node id: {node_id}")

        ports = attrs.pop("ports", None)
        for key, value in attrs.items():
            if key in {"id"}:
                continue
            node[key] = value

        if ports is None:
            return

        existing_ports = {port["id"]: port for port in node.get("ports", [])}
        for port in ports:
            port_id = port.get("id")
            if port_id not in existing_ports:
                raise KeyError(f"unknown port id: {port_id}")
            unsupported_keys = set(port.keys()) - {"id", "ip", "cidr"}
            if unsupported_keys:
                raise KeyError(f"unsupported port fields for update_node: {sorted(unsupported_keys)}")
            target = existing_ports[port_id]
            if "ip" in port:
                target["ip"] = port["ip"] or ""
            if "cidr" in port:
                target["cidr"] = port["cidr"] or ""

    def remove_link(self, link_id: str) -> None:
        links = self._working.get("links", [])
        for index, link in enumerate(list(links)):
            if link.get("id") == link_id:
                del links[index]
                return
        raise KeyError(f"unknown link id: {link_id}")

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
    ) -> None:
        link = self._find_link(link_id)
        if link is None:
            raise KeyError(f"unknown link id: {link_id}")

        self._ensure_endpoint(
            port_id=from_port,
            node_id=from_node,
            ip=from_ip,
            cidr=from_cidr,
        )
        self._ensure_endpoint(
            port_id=to_port,
            node_id=to_node,
            ip=to_ip,
            cidr=to_cidr,
        )
        link["from_port"] = from_port
        link["to_port"] = to_port
        link["id"] = f"{from_port}--{to_port}"

    def remove_node(self, node_id: str, *, cascade: bool = True) -> None:
        node = self._find_node(node_id)
        if node is None:
            raise KeyError(f"unknown node id: {node_id}")

        ports = node.get("ports", []) or []
        port_ids = {port.get("id") for port in ports}
        links = self._working.get("links", []) or []
        incident_links = [
            link
            for link in links
            if link.get("from_port") in port_ids or link.get("to_port") in port_ids
        ]
        if not cascade:
            if ports or incident_links:
                raise ValueError(f"node '{node_id}' still has ports or links")
        else:
            self._working["links"] = [
                link
                for link in links
                if link.get("from_port") not in port_ids and link.get("to_port") not in port_ids
            ]

        self._working["nodes"] = [item for item in self._working.get("nodes", []) if item.get("id") != node_id]

    def _ensure_endpoint(self, *, port_id: str, node_id: str | None, ip: str, cidr: str) -> None:
        for node in self._working.get("nodes", []):
            for port in node.get("ports", []):
                if port["id"] == port_id:
                    if ip:
                        port["ip"] = ip
                    if cidr:
                        port["cidr"] = cidr
                    return
        if node_id is None:
            raise KeyError(
                f"unknown port id {port_id!r}; provide the owning node id on the matching add_link side to create it"
            )
        self._add_port(node_id, port_id, ip, cidr)

    def _add_port(self, node_id: str, port_id: str, ip: str = "", cidr: str = "") -> None:
        node = self._find_node(node_id)
        if node is None:
            raise KeyError(f"unknown node id: {node_id}")
        node.setdefault("ports", []).append(
            {
                "id": port_id,
                "ip": ip,
                "cidr": cidr,
            }
        )

    def _find_node(self, node_id: str) -> dict[str, Any] | None:
        for node in self._working.get("nodes", []):
            if node.get("id") == node_id:
                return node
        return None

    def _find_link(self, link_id: str) -> dict[str, Any] | None:
        for link in self._working.get("links", []):
            if link.get("id") == link_id:
                return link
        return None

    @staticmethod
    def _links_contain_pair(links: list[dict[str, Any]] | None, a: str, b: str) -> bool:
        for link in links or []:
            if {link.get("from_port"), link.get("to_port")} == {a, b}:
                return True
        return False

    def _has_link_between(self, a: str, b: str) -> bool:
        return self._links_contain_pair(self._working.get("links"), a, b)

    def commit(self, levels: list[str] | None = None) -> dict[str, Any]:
        normalized = self._runtime.from_json(self._working).to_json()
        report = _run_validators(normalized, levels)
        if not report.ok:
            return {
                "ok": False,
                "issues": report.model_dump(mode="json")["issues"],
                "change_map": {},
            }
        self._runtime._payload = normalized
        return {"ok": True, "issues": [], "change_map": {}}

    def rollback(self) -> None:
        self._working = self._runtime.to_json()


def _run_validators(tgraph: dict[str, Any], levels: list[str] | None) -> ValidationReport:
    if not levels:
        return run_default_validators(tgraph)

    level_map = {
        "f1": f1_format,
        "f2": f2_schema,
        "f3": f3_consistency,
        "f4": f4_intent,
    }
    issues: list[ValidationIssue] = []
    for level in levels:
        fn = level_map.get(level)
        if fn is None:
            issues.append(
                ValidationIssue(
                    code="unknown_validator_level",
                    message=f"unknown validator level: {level}",
                    severity="error",
                    provenance={"layer": "f1", "source": "builtin"},
                )
            )
            continue
        issues.extend(ValidationIssue.model_validate(item) for item in fn(tgraph))

    return ValidationReport(ok=not any(item.severity == "error" for item in issues), issues=issues)
