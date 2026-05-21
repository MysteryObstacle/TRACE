from __future__ import annotations

from typing import Any

from tgraph.core.graph import TGraph
from tgraph.core.normalize import normalize_graph
from tgraph.core.stage import ensure_stage
from tgraph.operations.patch.diff import append_unique, empty_diff
from tgraph.operations.patch.errors import PatchConflictError, PatchError, PatchSchemaError, error_payload
from tgraph.operations.patch.result import PatchResult
from tgraph.operations.patch.schema import TGraphPatch
from tgraph.operations.validate import ValidationPolicy, validate_graph


def apply_patch(
    graph: TGraph | dict[str, Any],
    patch: TGraphPatch | dict[str, Any],
    *,
    validate: bool = True,
    include_graph: bool = False,
) -> PatchResult:
    current = graph if isinstance(graph, TGraph) else TGraph.model_validate(graph)
    parsed = patch if isinstance(patch, TGraphPatch) else TGraphPatch.from_json(patch)
    if not isinstance(parsed, TGraphPatch):
        if not parsed.ok:
            return PatchResult(ok=False, error=parsed.error)
        parsed = parsed.patch
    if parsed is None:
        return PatchResult(ok=False, error={"code": "patch_schema_error", "message": "invalid patch"})

    candidate = current.model_dump(mode="json")
    diff = empty_diff()
    accepted_ops: list[dict[str, Any]] = []

    for index, op in enumerate(parsed.graph_patch):
        name = op["op"]
        try:
            _apply_op(candidate, op, diff)
            accepted_ops.append({"section": "graph_patch", "index": index, "op": name})
        except PatchError as exc:
            return PatchResult(
                ok=False,
                accepted_ops=accepted_ops,
                rejected_ops=[{"section": "graph_patch", "index": index, "op": name, "error": error_payload(exc)}],
                diff=diff,
                error=error_payload(exc),
            )

    candidate_graph = normalize_graph(candidate)
    validation = validate_graph(candidate_graph, ValidationPolicy(levels=["f1", "f2", "f3", "f4"])) if validate else None
    ok = validation.ok if validation is not None else True
    return PatchResult(
        ok=ok,
        would_commit=ok,
        accepted_ops=accepted_ops,
        diff=diff,
        validation=validation,
        graph=candidate_graph if include_graph and ok else None,
        error=None if ok else {"code": "validation_failed", "message": "validation failed"},
    )


def _apply_op(graph: dict[str, Any], op: dict[str, Any], diff: dict[str, Any]) -> None:
    name = op["op"]
    if name == "ensure_node":
        _ensure_node(graph, op, diff)
    elif name == "ensure_port":
        _ensure_port(graph, op, diff)
    elif name == "ensure_link":
        _ensure_link(graph, op, diff)
    elif name == "remove_node":
        _remove_node(graph, op, diff)
    elif name == "remove_port":
        _remove_port(graph, op, diff)
    elif name == "remove_link":
        _remove_link(graph, op, diff)
    elif name == "set_stage":
        stage = ensure_stage(_required_str(op, "stage"))
        if graph.get("stage") != stage:
            graph["stage"] = stage
            diff["stage_changed"] = True
    else:
        raise PatchSchemaError(f"unknown graph op: {name}")


def _ensure_node(graph: dict[str, Any], op: dict[str, Any], diff: dict[str, Any]) -> None:
    node_id = _required_str(op, "id")
    existing = _find_node(graph, node_id)
    if existing is None:
        node = {
            "id": node_id,
            "type": _required_str(op, "type"),
            "label": _required_str(op, "label"),
            "ports": [],
            "image": op.get("image"),
            "flavor": op.get("flavor"),
        }
        graph.setdefault("nodes", []).append(node)
        append_unique(diff["nodes_added"], node_id)
        return

    changed = False
    for key in ("type", "label", "image", "flavor"):
        if key in op and existing.get(key) != op.get(key):
            existing[key] = op.get(key)
            changed = True
    if changed:
        append_unique(diff["nodes_updated"], node_id)


def _ensure_port(graph: dict[str, Any], op: dict[str, Any], diff: dict[str, Any]) -> None:
    node_id = _required_str(op, "node")
    port_id = _required_str(op, "port")
    node = _require_node(graph, node_id)
    existing = _find_port(node, port_id)
    if existing is None:
        node.setdefault("ports", []).append({"id": port_id, "ip": op.get("ip", ""), "cidr": op.get("cidr", "")})
        append_unique(diff["ports_added"], f"{node_id}.{port_id}")
        return

    changed = False
    for key in ("ip", "cidr"):
        if key in op and existing.get(key, "") != op.get(key, ""):
            existing[key] = op.get(key, "")
            changed = True
    if changed:
        append_unique(diff["ports_updated"], f"{node_id}.{port_id}")


def _ensure_link(graph: dict[str, Any], op: dict[str, Any], diff: dict[str, Any]) -> None:
    endpoint_a = _endpoint(op.get("a"), "a")
    endpoint_b = _endpoint(op.get("b"), "b")
    if endpoint_a["port"] == endpoint_b["port"]:
        raise PatchConflictError("link endpoints must use two different ports")

    _ensure_endpoint_port(graph, endpoint_a, diff)
    _ensure_endpoint_port(graph, endpoint_b, diff)

    port_a = endpoint_a["port"]
    port_b = endpoint_b["port"]
    target_pair = {port_a, port_b}
    incident = [
        link
        for link in graph.get("links", [])
        if (link.get("from_port") in target_pair or link.get("to_port") in target_pair)
        and {link.get("from_port"), link.get("to_port")} != target_pair
    ]
    if incident and not bool(op.get("reconnect", False)):
        raise PatchConflictError(f"one or more endpoint ports are already connected: {[link.get('id') for link in incident]}")
    if incident:
        for link in list(incident):
            _delete_link(graph, link, diff)

    _update_endpoint_addressing(graph, endpoint_a, diff)
    _update_endpoint_addressing(graph, endpoint_b, diff)

    if _find_link_between(graph, port_a, port_b) is None:
        link_id = _link_id(port_a, port_b)
        graph.setdefault("links", []).append({"id": link_id, "from_port": port_a, "to_port": port_b})
        append_unique(diff["links_added"], link_id)


def _remove_node(graph: dict[str, Any], op: dict[str, Any], diff: dict[str, Any]) -> None:
    node_id = _required_str(op, "id")
    node = _require_node(graph, node_id)
    port_ids = {port["id"] for port in node.get("ports", [])}
    incident = [link for link in graph.get("links", []) if link.get("from_port") in port_ids or link.get("to_port") in port_ids]
    if (node.get("ports") or incident) and not bool(op.get("cascade", False)):
        raise PatchConflictError(f"node has ports or incident links: {node_id}")
    for link in list(incident):
        _delete_link(graph, link, diff)
    graph["nodes"] = [item for item in graph.get("nodes", []) if item.get("id") != node_id]
    append_unique(diff["nodes_removed"], node_id)


def _remove_port(graph: dict[str, Any], op: dict[str, Any], diff: dict[str, Any]) -> None:
    node_id = _required_str(op, "node")
    port_id = _required_str(op, "port")
    node = _require_node(graph, node_id)
    if _find_port(node, port_id) is None:
        raise PatchConflictError(f"unknown port id: {port_id}")
    incident = [link for link in graph.get("links", []) if port_id in {link.get("from_port"), link.get("to_port")}]
    if incident and not bool(op.get("cascade", False)):
        raise PatchConflictError(f"port has incident links: {port_id}")
    for link in list(incident):
        _delete_link(graph, link, diff)
    node["ports"] = [port for port in node.get("ports", []) if port.get("id") != port_id]
    append_unique(diff["ports_removed"], f"{node_id}.{port_id}")


def _remove_link(graph: dict[str, Any], op: dict[str, Any], diff: dict[str, Any]) -> None:
    link_id = _required_str(op, "id")
    for link in list(graph.get("links", [])):
        if link.get("id") == link_id:
            _delete_link(graph, link, diff)
            return
    raise PatchConflictError(f"unknown link id: {link_id}")


def _ensure_endpoint_port(graph: dict[str, Any], endpoint: dict[str, str], diff: dict[str, Any]) -> None:
    owner = _port_owner_map(graph).get(endpoint["port"])
    if owner is not None:
        if endpoint.get("node") and owner != endpoint["node"]:
            raise PatchConflictError(f"port {endpoint['port']} belongs to {owner}, not {endpoint['node']}")
        return
    if not endpoint.get("node"):
        raise PatchConflictError(f"unknown port id {endpoint['port']}; endpoint must include node")
    _ensure_port(
        graph,
        {
            "op": "ensure_port",
            "node": endpoint["node"],
            "port": endpoint["port"],
            "ip": endpoint.get("ip", ""),
            "cidr": endpoint.get("cidr", ""),
        },
        diff,
    )


def _update_endpoint_addressing(graph: dict[str, Any], endpoint: dict[str, str], diff: dict[str, Any]) -> None:
    owner = _port_owner_map(graph).get(endpoint["port"])
    if owner is None:
        return
    op = {"op": "ensure_port", "node": owner, "port": endpoint["port"]}
    for key in ("ip", "cidr"):
        if key in endpoint:
            op[key] = endpoint[key]
    _ensure_port(graph, op, diff)


def _find_node(graph: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    for node in graph.get("nodes", []):
        if node.get("id") == node_id:
            return node
    return None


def _require_node(graph: dict[str, Any], node_id: str) -> dict[str, Any]:
    node = _find_node(graph, node_id)
    if node is None:
        raise PatchConflictError(f"unknown node id: {node_id}")
    return node


def _find_port(node: dict[str, Any], port_id: str) -> dict[str, Any] | None:
    for port in node.get("ports", []):
        if port.get("id") == port_id:
            return port
    return None


def _find_link_between(graph: dict[str, Any], port_a: str, port_b: str) -> dict[str, Any] | None:
    pair = {port_a, port_b}
    for link in graph.get("links", []):
        if {link.get("from_port"), link.get("to_port")} == pair:
            return link
    return None


def _delete_link(graph: dict[str, Any], link: dict[str, Any], diff: dict[str, Any]) -> None:
    graph["links"] = [item for item in graph.get("links", []) if item is not link]
    append_unique(diff["links_removed"], str(link.get("id") or _link_id(link["from_port"], link["to_port"])))


def _port_owner_map(graph: dict[str, Any]) -> dict[str, str]:
    return {
        str(port.get("id")): str(node.get("id"))
        for node in graph.get("nodes", [])
        for port in node.get("ports", [])
    }


def _endpoint(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise PatchSchemaError(f"endpoint {label} must be an object")
    endpoint = {"port": _required_str(value, "port")}
    if value.get("node") is not None:
        endpoint["node"] = str(value["node"])
    for key in ("ip", "cidr"):
        if key in value and value[key] is not None:
            endpoint[key] = str(value[key])
    return endpoint


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if value is None or str(value).strip() == "":
        raise PatchSchemaError(f"{key} is required")
    return str(value)


def _link_id(port_a: str, port_b: str) -> str:
    a, b = sorted((port_a, port_b))
    return f"{a}--{b}"

