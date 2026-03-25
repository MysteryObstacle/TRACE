from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.contracts import ValidationIssue
from stages.ground.normalize import expand_node_patterns
from tools.tgraph.model import Link, Node, Port, TGraph, ensure_tgraph
from tools.tgraph.validate.runner import validate_tgraph_payload


class PatchResult(BaseModel):
    ok: bool
    graph: dict[str, Any] | None
    issues: list[ValidationIssue] = Field(default_factory=list)


def patch(graph: TGraph | dict[str, Any], ops: list[dict[str, Any]]) -> PatchResult:
    try:
        working = ensure_tgraph(graph).model_dump(mode="json")
    except Exception as exc:
        return PatchResult(
            ok=False,
            graph=None,
            issues=[_issue("patch_invalid_graph", str(exc), "patch")],
        )

    for op in ops:
        op_name = op.get("op")
        if op_name in {"add_node", "add_nodes"}:
            outcome = _add_node(working, op)
        elif op_name in {"remove_node", "remove_nodes"}:
            outcome = _remove_nodes(working, op)
        elif op_name == "update_node":
            outcome = _update_node(working, op)
        elif op_name == "add_port":
            outcome = _add_port(working, op)
        elif op_name == "expand_nodes_from_pattern":
            outcome = _expand_nodes_from_pattern(working, op)
        elif op_name == "batch_update_nodes":
            outcome = _batch_update_nodes(working, op)
        elif op_name == "connect_nodes":
            outcome = _connect_nodes(working, op)
        elif op_name == "disconnect_nodes":
            outcome = _disconnect_nodes(working, op)
        elif op_name in {"add_link", "add_edge"}:
            outcome = _add_link(working, op)
        else:
            outcome = _failure("patch_unknown_op", f"unsupported patch op: {op_name}")

        if outcome is not None:
            return outcome

    validation_issues = [ValidationIssue.model_validate(item) for item in validate_tgraph_payload(working)]
    if validation_issues:
        return PatchResult(ok=False, graph=None, issues=validation_issues)

    return PatchResult(ok=True, graph=working, issues=[])


def _add_node(working: dict[str, Any], op: dict[str, Any]) -> PatchResult | None:
    if op.get("op") == "add_nodes":
        values = op.get("values") or []
        if not isinstance(values, list) or not values:
            return _failure("patch_missing_nodes", "add_nodes requires values")
        for value in values:
            outcome = _add_node(working, {"value": value})
            if outcome is not None:
                return outcome
        return None

    value = _normalize_node_payload(op.get("value") or {})
    try:
        node = Node.model_validate(value)
    except ValidationError as exc:
        return PatchResult(ok=False, graph=None, issues=[_issue("patch_invalid_node", exc.errors()[0]["msg"], "patch")])

    working.setdefault("nodes", []).append(node.model_dump(mode="json"))
    return None


def _remove_nodes(working: dict[str, Any], op: dict[str, Any]) -> PatchResult | None:
    node_ids = [str(node_id) for node_id in op.get("node_ids", [])]
    if not node_ids:
        return _failure("patch_missing_node_ids", "remove_nodes requires node_ids")

    nodes = working.setdefault("nodes", [])
    index_by_id = {node.get("id"): index for index, node in enumerate(nodes)}
    missing = [node_id for node_id in node_ids if node_id not in index_by_id]
    if missing:
        return PatchResult(
            ok=False,
            graph=None,
            issues=[_issue("patch_node_not_found", "remove_nodes requires existing nodes", "patch", targets=[f"node:{item}" for item in missing])],
        )

    removed_ids = set(node_ids)
    removed_port_ids = {
        port.get("id", "")
        for node in nodes
        if node.get("id") in removed_ids
        for port in node.get("ports", [])
    }
    working["nodes"] = [node for node in nodes if node.get("id") not in removed_ids]
    working["links"] = [
        link
        for link in working.get("links", [])
        if link.get("from_port") not in removed_port_ids
        and link.get("to_port") not in removed_port_ids
        and link.get("from_node") not in removed_ids
        and link.get("to_node") not in removed_ids
    ]
    return None


def _add_link(working: dict[str, Any], op: dict[str, Any]) -> PatchResult | None:
    value = dict(op.get("value") or {})
    port_owner = _build_port_owner(working)
    from_port = value.get("from_port")
    to_port = value.get("to_port")

    missing_targets: list[str] = []
    if from_port not in port_owner:
        missing_targets.append(f"port:{from_port}")
    if to_port not in port_owner:
        missing_targets.append(f"port:{to_port}")
    if missing_targets:
        return PatchResult(
            ok=False,
            graph=None,
            issues=[_issue("patch_link_endpoint_not_found", "link endpoints must reference existing ports", "patch", targets=missing_targets)],
        )

    value.setdefault("from_node", port_owner[from_port])
    value.setdefault("to_node", port_owner[to_port])

    try:
        link = Link.model_validate(value)
    except ValidationError as exc:
        return PatchResult(ok=False, graph=None, issues=[_issue("patch_invalid_link", exc.errors()[0]["msg"], "patch")])

    working.setdefault("links", []).append(link.model_dump(mode="json"))
    return None


def _connect_nodes(working: dict[str, Any], op: dict[str, Any]) -> PatchResult | None:
    from_endpoint = dict(op.get("from") or {})
    to_endpoint = dict(op.get("to") or {})

    from_node_id = str(from_endpoint.get("node_id") or "")
    to_node_id = str(to_endpoint.get("node_id") or "")
    if not from_node_id or not to_node_id:
        return _failure("patch_missing_target", "connect_nodes requires from.node_id and to.node_id")

    from_port_id_or_issue = _ensure_endpoint_port(working, from_node_id, from_endpoint.get("port"))
    if isinstance(from_port_id_or_issue, PatchResult):
        return from_port_id_or_issue
    to_port_id_or_issue = _ensure_endpoint_port(working, to_node_id, to_endpoint.get("port"))
    if isinstance(to_port_id_or_issue, PatchResult):
        return to_port_id_or_issue

    from_port_id = from_port_id_or_issue
    to_port_id = to_port_id_or_issue
    linked_targets: list[str] = []
    if _port_is_linked(working, from_port_id):
        linked_targets.append(f"port:{from_port_id}")
    if _port_is_linked(working, to_port_id):
        linked_targets.append(f"port:{to_port_id}")
    if linked_targets:
        return PatchResult(
            ok=False,
            graph=None,
            issues=[_issue("patch_port_already_linked", "ports must be disconnected before reuse", "patch", targets=linked_targets)],
        )

    return _add_link(
        working,
        {
            "value": {
                "id": f"{from_port_id}--{to_port_id}",
                "from_port": from_port_id,
                "to_port": to_port_id,
                "from_node": from_node_id,
                "to_node": to_node_id,
            }
        },
    )


def _disconnect_nodes(working: dict[str, Any], op: dict[str, Any]) -> PatchResult | None:
    from_endpoint = dict(op.get("from") or {})
    to_endpoint = dict(op.get("to") or {})

    from_node_id = str(from_endpoint.get("node_id") or "")
    to_node_id = str(to_endpoint.get("node_id") or "")
    from_port_id = str(from_endpoint.get("port_id") or "")
    to_port_id = str(to_endpoint.get("port_id") or "")
    if not from_node_id or not to_node_id or not from_port_id or not to_port_id:
        return _failure("patch_missing_target", "disconnect_nodes requires node_id and port_id on both endpoints")

    port_owner = _build_port_owner(working)
    mismatches: list[str] = []
    if port_owner.get(from_port_id) != from_node_id:
        mismatches.append(f"port:{from_port_id}")
    if port_owner.get(to_port_id) != to_node_id:
        mismatches.append(f"port:{to_port_id}")
    if mismatches:
        return PatchResult(
            ok=False,
            graph=None,
            issues=[_issue("patch_disconnect_endpoint_mismatch", "disconnect endpoints must match current port owners", "patch", targets=mismatches)],
        )

    links = working.setdefault("links", [])
    for index, link in enumerate(links):
        endpoints = {(link.get("from_port"), link.get("to_port")), (link.get("to_port"), link.get("from_port"))}
        if (from_port_id, to_port_id) in endpoints:
            del links[index]
            return None

    return PatchResult(
        ok=False,
        graph=None,
        issues=[_issue("patch_link_not_found", "disconnect_nodes requires an existing link", "patch", targets=[f"port:{from_port_id}", f"port:{to_port_id}"])],
    )


def _update_node(working: dict[str, Any], op: dict[str, Any]) -> PatchResult | None:
    node_id = str(op.get("node_id") or "")
    if not node_id:
        return _failure("patch_missing_node_id", "update_node requires node_id")

    nodes = working.setdefault("nodes", [])
    index_by_id = {node.get("id"): index for index, node in enumerate(nodes)}
    if node_id not in index_by_id:
        return PatchResult(
            ok=False,
            graph=None,
            issues=[_issue("patch_node_not_found", "update_node requires an existing node", "patch", targets=[f"node:{node_id}"])],
        )

    node_index = index_by_id[node_id]
    return _apply_node_update(working, node_index, dict(op.get("changes") or {}), dict(op.get("remove") or {}))


def _add_port(working: dict[str, Any], op: dict[str, Any]) -> PatchResult | None:
    node_id = str(op.get("node_id") or "")
    if not node_id:
        return _failure("patch_missing_node_id", "add_port requires node_id")

    nodes = working.setdefault("nodes", [])
    index_by_id = {node.get("id"): index for index, node in enumerate(nodes)}
    if node_id not in index_by_id:
        return PatchResult(
            ok=False,
            graph=None,
            issues=[_issue("patch_node_not_found", "add_port requires an existing node", "patch", targets=[f"node:{node_id}"])],
        )

    try:
        port = Port.model_validate(op.get("value") or {})
    except ValidationError as exc:
        return PatchResult(ok=False, graph=None, issues=[_issue("patch_invalid_port", exc.errors()[0]["msg"], "patch")])

    node_index = index_by_id[node_id]
    updated = dict(nodes[node_index])
    ports = list(updated.get("ports", []))
    ports.append(port.model_dump(mode="json"))
    updated["ports"] = ports
    try:
        node = Node.model_validate(updated)
    except ValidationError as exc:
        return PatchResult(ok=False, graph=None, issues=[_issue("patch_invalid_node", exc.errors()[0]["msg"], "patch")])

    nodes[node_index] = node.model_dump(mode="json")
    return None


def _expand_nodes_from_pattern(working: dict[str, Any], op: dict[str, Any]) -> PatchResult | None:
    pattern = str(op.get("pattern") or "")
    if not pattern:
        return _failure("patch_missing_pattern", "expand_nodes_from_pattern requires a pattern")

    node_type = str(op.get("node_type") or "computer")
    for node_id in expand_node_patterns([pattern]):
        outcome = _add_node(
            working,
            {
                "value": {
                    "id": node_id,
                    "type": node_type,
                    "label": node_id,
                    "ports": [],
                    "image": None,
                    "flavor": None,
                }
            },
        )
        if outcome is not None:
            return outcome
    return None


def _batch_update_nodes(working: dict[str, Any], op: dict[str, Any]) -> PatchResult | None:
    node_ids = [str(node_id) for node_id in op.get("node_ids", [])]
    if not node_ids:
        return _failure("patch_missing_node_ids", "batch_update_nodes requires node_ids")

    changes = dict(op.get("changes") or {})
    remove = dict(op.get("remove") or {})
    nodes = working.setdefault("nodes", [])
    index_by_id = {node.get("id"): index for index, node in enumerate(nodes)}
    missing = [node_id for node_id in node_ids if node_id not in index_by_id]
    if missing:
        return PatchResult(
            ok=False,
            graph=None,
            issues=[_issue("patch_node_not_found", "batch update requires existing nodes", "patch", targets=[f"node:{item}" for item in missing])],
        )

    for node_id in node_ids:
        node_index = index_by_id[node_id]
        outcome = _apply_node_update(working, node_index, changes, remove)
        if outcome is not None:
            return outcome
    return None


def _apply_node_update(working: dict[str, Any], node_index: int, changes: dict[str, Any], remove: dict[str, Any]) -> PatchResult | None:
    nodes = working.setdefault("nodes", [])
    current = dict(nodes[node_index])
    node_id = str(current.get("id") or "")
    normalized_changes = _normalize_node_payload(dict(changes))
    if "id" in normalized_changes and normalized_changes["id"] != node_id:
        return _failure("patch_invalid_update_payload", "update_node must not modify node id")

    updated = dict(current)
    for field in ("type", "label", "image", "flavor"):
        if field in normalized_changes:
            updated[field] = normalized_changes[field]

    change_ports = normalized_changes.get("ports")
    remove_ports = [str(port_id) for port_id in remove.get("ports", [])]
    if change_ports is not None and not isinstance(change_ports, list):
        return _failure("patch_invalid_update_payload", "changes.ports must be a list")
    if remove.get("ports") is not None and not isinstance(remove.get("ports"), list):
        return _failure("patch_invalid_update_payload", "remove.ports must be a list")

    changed_port_ids = {str(port.get("id")) for port in change_ports or [] if isinstance(port, dict)}
    if changed_port_ids.intersection(remove_ports):
        return _failure("patch_invalid_update_payload", "the same port cannot be changed and removed in one update")

    ports = [dict(port) for port in current.get("ports", [])]
    if change_ports is not None:
        outcome = _upsert_ports(working, node_id, ports, change_ports)
        if outcome is not None:
            return outcome
    if remove_ports:
        outcome = _remove_ports(working, node_id, ports, remove_ports)
        if outcome is not None:
            return outcome

    updated["ports"] = ports
    try:
        node = Node.model_validate(updated)
    except ValidationError as exc:
        return PatchResult(ok=False, graph=None, issues=[_issue("patch_invalid_node", exc.errors()[0]["msg"], "patch")])
    nodes[node_index] = node.model_dump(mode="json")
    return None


def _ensure_endpoint_port(working: dict[str, Any], node_id: str, payload: Any) -> str | PatchResult:
    if not isinstance(payload, dict):
        return _failure("patch_invalid_port", "connect_nodes requires endpoint port payloads")

    nodes = working.setdefault("nodes", [])
    index_by_id = {node.get("id"): index for index, node in enumerate(nodes)}
    if node_id not in index_by_id:
        return PatchResult(
            ok=False,
            graph=None,
            issues=[_issue("patch_node_not_found", "connect_nodes requires existing endpoint nodes", "patch", targets=[f"node:{node_id}"])],
        )

    port_id = str(payload.get("id") or "")
    if not port_id:
        return _failure("patch_invalid_port", "endpoint ports require id")

    port_owner = _build_port_owner(working)
    owner = port_owner.get(port_id)
    if owner is not None and owner != node_id:
        return PatchResult(
            ok=False,
            graph=None,
            issues=[_issue("patch_port_owner_mismatch", "port id is already owned by another node", "patch", targets=[f"port:{port_id}", f"node:{owner}"])],
        )

    node_index = index_by_id[node_id]
    ports = [dict(port) for port in nodes[node_index].get("ports", [])]
    outcome = _upsert_ports(working, node_id, ports, [payload])
    if outcome is not None:
        return outcome

    updated = dict(nodes[node_index])
    updated["ports"] = ports
    try:
        node = Node.model_validate(updated)
    except ValidationError as exc:
        return PatchResult(ok=False, graph=None, issues=[_issue("patch_invalid_node", exc.errors()[0]["msg"], "patch")])
    nodes[node_index] = node.model_dump(mode="json")
    return port_id


def _upsert_ports(working: dict[str, Any], node_id: str, ports: list[dict[str, Any]], port_payloads: list[dict[str, Any]]) -> PatchResult | None:
    owner_map = _build_port_owner(working)
    existing_index = {port.get("id"): index for index, port in enumerate(ports)}

    for payload in port_payloads:
        if not isinstance(payload, dict):
            return _failure("patch_invalid_port", "ports updates must contain objects")

        port_id = str(payload.get("id") or "")
        if not port_id:
            return _failure("patch_invalid_port", "port updates require id")

        owner = owner_map.get(port_id)
        if owner is not None and owner != node_id:
            return PatchResult(
                ok=False,
                graph=None,
                issues=[_issue("patch_port_owner_mismatch", "port id is already owned by another node", "patch", targets=[f"port:{port_id}", f"node:{owner}"])],
            )

        if port_id in existing_index:
            merged = dict(ports[existing_index[port_id]])
            merged.update(payload)
            try:
                port = Port.model_validate(merged)
            except ValidationError as exc:
                return PatchResult(ok=False, graph=None, issues=[_issue("patch_invalid_port", exc.errors()[0]["msg"], "patch")])
            ports[existing_index[port_id]] = port.model_dump(mode="json")
        else:
            try:
                port = Port.model_validate(payload)
            except ValidationError as exc:
                return PatchResult(ok=False, graph=None, issues=[_issue("patch_invalid_port", exc.errors()[0]["msg"], "patch")])
            ports.append(port.model_dump(mode="json"))
            existing_index[port_id] = len(ports) - 1

    return None


def _remove_ports(working: dict[str, Any], node_id: str, ports: list[dict[str, Any]], remove_port_ids: list[str]) -> PatchResult | None:
    existing_ids = {port.get("id") for port in ports}
    for port_id in remove_port_ids:
        if port_id not in existing_ids:
            return PatchResult(
                ok=False,
                graph=None,
                issues=[_issue("patch_port_not_found", "remove requested a port that does not belong to the node", "patch", targets=[f"node:{node_id}", f"port:{port_id}"])],
            )
        if _port_is_linked(working, port_id):
            return PatchResult(
                ok=False,
                graph=None,
                issues=[_issue("patch_remove_connected_port_forbidden", "disconnect a port before removing it", "patch", targets=[f"node:{node_id}", f"port:{port_id}"])],
            )
        ports[:] = [port for port in ports if port.get("id") != port_id]
        existing_ids.discard(port_id)
    return None


def _port_is_linked(working: dict[str, Any], port_id: str) -> bool:
    return any(link.get("from_port") == port_id or link.get("to_port") == port_id for link in working.get("links", []))


def _build_port_owner(graph: dict[str, Any]) -> dict[str, str]:
    owners: dict[str, str] = {}
    for node in graph.get("nodes", []):
        node_id = node.get("id", "")
        for port in node.get("ports", []):
            owners.setdefault(port.get("id", ""), node_id)
    return owners


def _normalize_node_payload(value: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(value)
    type_aliases = {
        "firewall": "computer",
        "plc": "computer",
        "hmi": "computer",
        "server": "computer",
    }
    node_type = normalized.get("type")
    if isinstance(node_type, str):
        normalized["type"] = type_aliases.get(node_type.lower(), node_type)
    return normalized


def _failure(code: str, message: str) -> PatchResult:
    return PatchResult(ok=False, graph=None, issues=[_issue(code, message, "patch")])


def _issue(code: str, message: str, scope: str, *, targets: list[str] | None = None) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        message=message,
        severity="error",
        scope=scope,
        targets=targets or [],
        json_paths=[],
    )
