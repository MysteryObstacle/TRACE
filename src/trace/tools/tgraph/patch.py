from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from trace.tools.tgraph.runtime import TGraphRuntime
from trace.tools.tgraph.validate.f1_format import f1_format
from trace.tools.tgraph.validate.f2_schema import f2_schema
from trace.tools.tgraph.validate.f3_consistency import f3_consistency
from trace.tools.tgraph.validate.f4_intent import f4_intent
from trace.tools.tgraph.validate.types import ValidationIssue, ValidationReport


STAGE_FIELDS = {
    "logical": ("tgraph_logical", "logical_checkpoints", "logical_validator_script"),
    "physical": ("tgraph_physical", "physical_checkpoints", "physical_validator_script"),
}


class PatchError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_json(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def infer_artifact_stage(artifact: dict[str, Any]) -> str:
    matches = [stage for stage, (graph_field, _, _) in STAGE_FIELDS.items() if graph_field in artifact]
    if len(matches) != 1:
        raise ValueError("artifact stage is ambiguous or missing")
    return matches[0]


def apply_artifact_patch(
    artifact: dict[str, Any],
    patch: dict[str, Any],
    *,
    stage: str | None = None,
    dry_run: bool | None = None,
    include_artifact: bool | None = None,
) -> dict[str, Any]:
    if not isinstance(artifact, dict):
        return _error_result("artifact_shape_error", "artifact must be an object")
    if not isinstance(patch, dict):
        return _error_result("patch_schema_error", "patch must be an object")

    options = patch.get("options") or {}
    if not isinstance(options, dict):
        return _error_result("patch_schema_error", "patch options must be an object")

    try:
        selected_stage = stage or options.get("stage") or infer_artifact_stage(artifact)
        graph_field, checkpoints_field, validator_field = STAGE_FIELDS[str(selected_stage)]
    except (KeyError, ValueError) as exc:
        return _error_result("artifact_shape_error", str(exc))

    effective_dry_run = bool(options.get("dry_run") if dry_run is None else dry_run)
    effective_include_artifact = bool(options.get("include_artifact") if include_artifact is None else include_artifact)
    levels = options.get("validate") or ["f1", "f2", "f3", "f4"]

    candidate = deepcopy(artifact)
    if graph_field not in candidate:
        return _error_result("artifact_shape_error", f"artifact is missing graph field: {graph_field}")
    candidate.setdefault(checkpoints_field, [])
    candidate.setdefault(validator_field, None)
    diff = _empty_diff()
    accepted_ops: list[dict[str, Any]] = []
    rejected_ops: list[dict[str, Any]] = []

    try:
        candidate[graph_field] = TGraphRuntime.from_json(candidate[graph_field]).to_json()
        graph_accepted, graph_rejected = _apply_graph_patch(
            candidate[graph_field],
            _ops_list(patch.get("graph_patch"), "graph_patch"),
            diff,
        )
        accepted_ops.extend(graph_accepted)
        rejected_ops.extend(graph_rejected)

        if not rejected_ops:
            checkpoint_accepted, checkpoint_rejected = _apply_checkpoint_patch(
                candidate[checkpoints_field],
                _ops_list(patch.get("checkpoint_patch"), "checkpoint_patch"),
                diff,
            )
            accepted_ops.extend(checkpoint_accepted)
            rejected_ops.extend(checkpoint_rejected)

        if not rejected_ops and patch.get("validator_patch") is not None:
            candidate[validator_field] = _apply_validator_patch(candidate.get(validator_field), patch.get("validator_patch"), diff)
            accepted_ops.append({"section": "validator_patch", "index": 0, "op": "replace_script"})
    except PatchError as exc:
        rejected_ops.append({"section": "patch", "index": 0, "op": None, "error": exc.to_json()})
    except Exception as exc:
        return _error_result("artifact_shape_error", str(exc))

    if rejected_ops:
        first_error = rejected_ops[0]["error"]
        result = _base_result()
        result["accepted_ops"] = accepted_ops
        result["rejected_ops"] = rejected_ops
        result["diff"] = diff
        result["error"] = {"code": first_error["code"], "message": "one or more patch operations were rejected"}
        return result

    try:
        candidate[graph_field] = TGraphRuntime.from_json(candidate[graph_field]).to_json()
    except Exception as exc:
        return _error_result("artifact_shape_error", str(exc))

    validation = _validate_candidate(
        candidate[graph_field],
        stage=str(selected_stage),
        checkpoints_field=checkpoints_field,
        validator_field=validator_field,
        candidate=candidate,
        levels=levels,
    )

    result = _base_result()
    result["ok"] = bool(validation["ok"])
    result["committed"] = bool(validation["ok"] and not effective_dry_run)
    result["accepted_ops"] = accepted_ops
    result["diff"] = diff
    result["validation"] = validation
    if effective_include_artifact:
        result["artifact"] = candidate
    if not validation["ok"]:
        result["error"] = {"code": "validation_failed", "message": "validation failed"}
    return result


def _apply_graph_patch(
    graph: dict[str, Any],
    ops: list[dict[str, Any]],
    diff: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, op in enumerate(ops):
        name = op.get("op")
        try:
            if name == "ensure_node":
                _ensure_node(graph, op, diff)
            elif name == "ensure_link":
                _ensure_link(graph, op, diff)
            elif name == "remove_link":
                _remove_link(graph, op, diff)
            elif name == "remove_node":
                _remove_node(graph, op, diff)
            else:
                raise PatchError("patch_schema_error", f"unknown graph op: {name}")
            accepted.append({"section": "graph_patch", "index": index, "op": str(name)})
        except PatchError as exc:
            rejected.append({"section": "graph_patch", "index": index, "op": name, "error": exc.to_json()})
            break
    return accepted, rejected


def _ensure_node(graph: dict[str, Any], op: dict[str, Any], diff: dict[str, Any]) -> None:
    node_id = _required_str(op, "id")
    nodes = graph.setdefault("nodes", [])
    existing = _find_node(graph, node_id)
    allowed = {"type", "label", "image", "flavor"}
    if existing is None:
        node_type = _required_str(op, "type")
        label = _required_str(op, "label")
        node = {
            "id": node_id,
            "type": node_type,
            "label": label,
            "ports": [],
            "image": op.get("image"),
            "flavor": op.get("flavor"),
        }
        nodes.append(node)
        _append_unique(diff["nodes_added"], node_id)
        return

    changed = False
    for key in allowed:
        if key in op and existing.get(key) != op.get(key):
            existing[key] = op.get(key)
            changed = True
    if changed:
        _append_unique(diff["nodes_updated"], node_id)


def _ensure_link(graph: dict[str, Any], op: dict[str, Any], diff: dict[str, Any]) -> None:
    endpoint_a = _endpoint(op.get("a"), "a")
    endpoint_b = _endpoint(op.get("b"), "b")
    port_a = endpoint_a["port"]
    port_b = endpoint_b["port"]
    if port_a == port_b:
        raise PatchError("op_conflict", "link endpoints must use two different ports")

    reconnect = bool(op.get("reconnect", False))
    _ensure_endpoint_port(graph, endpoint_a, diff)
    _ensure_endpoint_port(graph, endpoint_b, diff)

    links = graph.setdefault("links", [])
    pair = {port_a, port_b}
    existing_target = _find_link_between(graph, port_a, port_b)
    incident = [
        link
        for link in links
        if (link.get("from_port") in pair or link.get("to_port") in pair) and set(_link_ports(link)) != pair
    ]
    if incident and not reconnect:
        raise PatchError("op_conflict", f"one or more endpoint ports are already connected: {[link.get('id') for link in incident]}")
    if incident and reconnect:
        for link in list(incident):
            _delete_link_object(graph, link, diff)
        links = graph.setdefault("links", [])

    _update_endpoint_addressing(graph, endpoint_a, diff)
    _update_endpoint_addressing(graph, endpoint_b, diff)

    if existing_target is None:
        links.append({"id": _link_id(port_a, port_b), "from_port": port_a, "to_port": port_b})
        _append_unique(diff["links_added"], _link_id(port_a, port_b))


def _remove_link(graph: dict[str, Any], op: dict[str, Any], diff: dict[str, Any]) -> None:
    link_id = _required_str(op, "id")
    for link in list(graph.get("links", [])):
        if link.get("id") == link_id:
            _delete_link_object(graph, link, diff)
            return
    raise PatchError("op_conflict", f"unknown link id: {link_id}")


def _remove_node(graph: dict[str, Any], op: dict[str, Any], diff: dict[str, Any]) -> None:
    node_id = _required_str(op, "id")
    cascade = bool(op.get("cascade", True))
    node = _find_node(graph, node_id)
    if node is None:
        raise PatchError("op_conflict", f"unknown node id: {node_id}")
    port_ids = {port.get("id") for port in node.get("ports", [])}
    incident = [link for link in graph.get("links", []) if link.get("from_port") in port_ids or link.get("to_port") in port_ids]
    if not cascade and (node.get("ports") or incident):
        raise PatchError("op_conflict", f"node has ports or incident links: {node_id}")
    for link in list(incident):
        _delete_link_object(graph, link, diff)
    graph["nodes"] = [item for item in graph.get("nodes", []) if item.get("id") != node_id]
    _append_unique(diff["nodes_removed"], node_id)


def _apply_checkpoint_patch(
    checkpoints: list[dict[str, Any]],
    ops: list[dict[str, Any]],
    diff: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, op in enumerate(ops):
        name = op.get("op")
        try:
            if name == "ensure_checkpoint":
                _ensure_checkpoint(checkpoints, op, diff)
            elif name == "remove_checkpoint":
                _remove_checkpoint(checkpoints, op, diff)
            else:
                raise PatchError("patch_schema_error", f"unknown checkpoint op: {name}")
            accepted.append({"section": "checkpoint_patch", "index": index, "op": str(name)})
        except PatchError as exc:
            rejected.append({"section": "checkpoint_patch", "index": index, "op": name, "error": exc.to_json()})
            break
    return accepted, rejected


def _ensure_checkpoint(checkpoints: list[dict[str, Any]], op: dict[str, Any], diff: dict[str, Any]) -> None:
    checkpoint_id = _required_str(op, "id")
    existing = _find_checkpoint(checkpoints, checkpoint_id)
    allowed = {"func", "description", "constraint_ids", "args"}
    if existing is None:
        func = _required_str(op, "func")
        item = {
            "id": checkpoint_id,
            "func": func,
            "description": op.get("description", ""),
            "constraint_ids": list(op.get("constraint_ids") or []),
            "args": dict(op.get("args") or {}),
        }
        checkpoints.append(item)
        _append_unique(diff["checkpoints_added"], checkpoint_id)
        return
    changed = False
    for key in allowed:
        if key in op and existing.get(key) != op.get(key):
            existing[key] = op.get(key)
            changed = True
    if changed:
        _append_unique(diff["checkpoints_updated"], checkpoint_id)


def _remove_checkpoint(checkpoints: list[dict[str, Any]], op: dict[str, Any], diff: dict[str, Any]) -> None:
    checkpoint_id = _required_str(op, "id")
    for index, item in enumerate(list(checkpoints)):
        if item.get("id") == checkpoint_id:
            del checkpoints[index]
            _append_unique(diff["checkpoints_removed"], checkpoint_id)
            return
    raise PatchError("op_conflict", f"unknown checkpoint id: {checkpoint_id}")


def _apply_validator_patch(current_script: str | None, validator_patch: Any, diff: dict[str, Any]) -> str | None:
    if not isinstance(validator_patch, dict):
        raise PatchError("patch_schema_error", "validator_patch must be an object")
    if validator_patch.get("op") != "replace_script":
        raise PatchError("patch_schema_error", f"unknown validator_patch op: {validator_patch.get('op')}")
    diff["validator_script_replaced"] = True
    return validator_patch.get("script")


def _validate_candidate(
    graph: dict[str, Any],
    *,
    stage: str,
    checkpoints_field: str,
    validator_field: str,
    candidate: dict[str, Any],
    levels: Any,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {checkpoints_field: candidate.get(checkpoints_field, [])}
    constraints_field = "logical_constraints" if stage == "logical" else "physical_constraints"
    if constraints_field in candidate:
        kwargs[constraints_field] = candidate.get(constraints_field) or []
    if candidate.get(validator_field) is not None:
        kwargs[validator_field] = candidate.get(validator_field)
    return _run_validators(graph, _levels_list(levels), **kwargs).model_dump(mode="json")


def _run_validators(tgraph: dict[str, Any], levels: list[str], **kwargs: Any) -> ValidationReport:
    level_map: dict[str, Callable[..., list[dict[str, Any]]]] = {
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
        issues.extend(ValidationIssue.model_validate(item) for item in fn(tgraph, **kwargs))
    return ValidationReport(ok=not any(item.severity == "error" for item in issues), issues=issues)


def _ensure_endpoint_port(graph: dict[str, Any], endpoint: dict[str, str], diff: dict[str, Any]) -> None:
    port_id = endpoint["port"]
    node_id = endpoint.get("node")
    owner = _port_owner_map(graph).get(port_id)
    if owner is not None:
        if node_id and owner != node_id:
            raise PatchError("op_conflict", f"port {port_id} belongs to {owner}, not {node_id}")
        return
    if not node_id:
        raise PatchError("op_conflict", f"unknown port id {port_id}; endpoint must include node")
    node = _find_node(graph, node_id)
    if node is None:
        raise PatchError("op_conflict", f"unknown node id: {node_id}")
    node.setdefault("ports", []).append({"id": port_id, "ip": endpoint.get("ip", ""), "cidr": endpoint.get("cidr", "")})
    _append_unique(diff["ports_added"], f"{node_id}.{port_id}")


def _update_endpoint_addressing(graph: dict[str, Any], endpoint: dict[str, str], diff: dict[str, Any]) -> None:
    port_id = endpoint["port"]
    owner = _port_owner_map(graph).get(port_id)
    if owner is None:
        return
    node = _find_node(graph, owner)
    if node is None:
        return
    for port in node.get("ports", []):
        if port.get("id") != port_id:
            continue
        changed = False
        for key in ("ip", "cidr"):
            if key in endpoint and port.get(key, "") != endpoint.get(key, ""):
                port[key] = endpoint.get(key, "")
                changed = True
        if changed:
            _append_unique(diff["ports_updated"], f"{owner}.{port_id}")
        return


def _find_node(graph: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    for node in graph.get("nodes", []):
        if node.get("id") == node_id:
            return node
    return None


def _find_checkpoint(checkpoints: list[dict[str, Any]], checkpoint_id: str) -> dict[str, Any] | None:
    for item in checkpoints:
        if item.get("id") == checkpoint_id:
            return item
    return None


def _find_link_between(graph: dict[str, Any], port_a: str, port_b: str) -> dict[str, Any] | None:
    target = {port_a, port_b}
    for link in graph.get("links", []):
        if set(_link_ports(link)) == target:
            return link
    return None


def _delete_link_object(graph: dict[str, Any], link: dict[str, Any], diff: dict[str, Any]) -> None:
    graph["links"] = [item for item in graph.get("links", []) if item is not link]
    _append_unique(diff["links_removed"], str(link.get("id") or _link_id(*_link_ports(link))))


def _port_owner_map(graph: dict[str, Any]) -> dict[str, str]:
    owners: dict[str, str] = {}
    for node in graph.get("nodes", []):
        for port in node.get("ports", []):
            owners[str(port.get("id"))] = str(node.get("id"))
    return owners


def _endpoint(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise PatchError("patch_schema_error", f"endpoint {label} must be an object")
    endpoint = dict(value)
    endpoint["port"] = _required_str(endpoint, "port")
    if "node" in endpoint and endpoint["node"] is not None:
        endpoint["node"] = str(endpoint["node"])
    for key in ("ip", "cidr"):
        if key in endpoint and endpoint[key] is not None:
            endpoint[key] = str(endpoint[key])
    return endpoint


def _ops_list(value: Any, field_name: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise PatchError("patch_schema_error", f"{field_name} must be a list")
    for item in value:
        if not isinstance(item, dict):
            raise PatchError("patch_schema_error", f"{field_name} items must be objects")
    return value


def _levels_list(value: Any) -> list[str]:
    if value is None:
        return ["f1", "f2", "f3", "f4"]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise PatchError("patch_schema_error", "validate option must be a list or comma-separated string")


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if value is None or str(value).strip() == "":
        raise PatchError("patch_schema_error", f"{key} is required")
    return str(value)


def _link_ports(link: dict[str, Any]) -> tuple[str, str]:
    return str(link.get("from_port")), str(link.get("to_port"))


def _link_id(port_a: str, port_b: str) -> str:
    a, b = sorted((port_a, port_b))
    return f"{a}--{b}"


def _append_unique(target: list[str], value: str) -> None:
    if value not in target:
        target.append(value)


def _empty_diff() -> dict[str, Any]:
    return {
        "nodes_added": [],
        "nodes_updated": [],
        "nodes_removed": [],
        "links_added": [],
        "links_removed": [],
        "ports_added": [],
        "ports_updated": [],
        "checkpoints_added": [],
        "checkpoints_updated": [],
        "checkpoints_removed": [],
        "validator_script_replaced": False,
    }


def _base_result() -> dict[str, Any]:
    return {
        "ok": False,
        "committed": False,
        "accepted_ops": [],
        "rejected_ops": [],
        "diff": _empty_diff(),
        "validation": None,
        "artifact": None,
        "error": None,
    }


def _error_result(code: str, message: str) -> dict[str, Any]:
    result = _base_result()
    result["error"] = {"code": code, "message": message}
    return result
