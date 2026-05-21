from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from tgraph import apply_patch as apply_standalone_patch

from trace.tools.tgraph.model import from_standalone_graph, to_standalone_graph
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
            stage=str(selected_stage),
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
    *,
    stage: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    adapted_ops: list[dict[str, Any]] = []
    for index, raw_op in enumerate(ops):
        name = raw_op.get("op")
        try:
            adapted_ops.append(_adapt_graph_op(raw_op))
        except PatchError as exc:
            return [], [{"section": "graph_patch", "index": index, "op": name, "error": exc.to_json()}]

    if not adapted_ops:
        return [], []

    standalone = to_standalone_graph(graph, stage=stage)
    result = apply_standalone_patch(
        standalone,
        {"graph_patch": adapted_ops},
        validate=False,
        include_graph=True,
    )

    accepted = list(result.accepted_ops)
    rejected = [_translate_rejected_op(item) for item in result.rejected_ops]
    if not result.ok:
        if rejected:
            return accepted, rejected
        error = _translate_graph_error(result.error or {"code": "patch_error", "message": "graph patch failed"})
        return accepted, [{"section": "graph_patch", "index": 0, "op": None, "error": error}]

    if result.graph is None:
        return accepted, [
            {
                "section": "graph_patch",
                "index": 0,
                "op": None,
                "error": {"code": "patch_error", "message": "graph patch did not return a candidate graph"},
            }
        ]

    _merge_graph_diff(diff, result.diff)
    profile = str(graph.get("profile") or "taal.default.v1")
    updated = from_standalone_graph(result.graph, profile=profile).model_dump(mode="json")
    graph.clear()
    graph.update(updated)
    return accepted, []


def _adapt_graph_op(op: dict[str, Any]) -> dict[str, Any]:
    name = op.get("op")
    if name == "set_stage":
        raise PatchError("patch_schema_error", "set_stage is only supported by standalone TGraph documents")
    if name not in {"ensure_node", "ensure_port", "ensure_link", "remove_node", "remove_port", "remove_link"}:
        raise PatchError("patch_schema_error", f"unknown graph op: {name}")
    adapted = dict(op)
    if name == "remove_node" and "cascade" not in adapted:
        adapted["cascade"] = True
    return adapted


def _merge_graph_diff(diff: dict[str, Any], graph_diff: dict[str, Any]) -> None:
    for key, value in graph_diff.items():
        if isinstance(value, list):
            target = diff.setdefault(key, [])
            for item in value:
                _append_unique(target, str(item))
        elif isinstance(value, bool):
            diff[key] = bool(diff.get(key, False) or value)
        else:
            diff[key] = value


def _translate_rejected_op(item: dict[str, Any]) -> dict[str, Any]:
    translated = dict(item)
    translated["error"] = _translate_graph_error(dict(translated.get("error") or {}))
    return translated


def _translate_graph_error(error: dict[str, Any]) -> dict[str, Any]:
    translated = dict(error)
    if translated.get("code") == "patch_conflict":
        translated["code"] = "op_conflict"
    return translated


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


def _find_checkpoint(checkpoints: list[dict[str, Any]], checkpoint_id: str) -> dict[str, Any] | None:
    for item in checkpoints:
        if item.get("id") == checkpoint_id:
            return item
    return None


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
        "ports_removed": [],
        "stage_changed": False,
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
