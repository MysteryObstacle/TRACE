from __future__ import annotations

import ast
from typing import Any, Callable

from trace.tools.tgraph.validate.intent_sdk import (
    IntentTGraphView,
    SAFE_BUILTINS,
    SDK_FUNCTIONS,
    SDK_GLOBALS,
)
from trace.tools.tgraph.validate.issues import issue


def f4_intent(tgraph: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
    checkpoints, script, checkpoint_json_path, script_artifact, constraints = _resolve_checkpoint_payload(kwargs)
    known_constraint_ids = _known_constraint_ids(constraints)
    if not checkpoints:
        return _missing_coverage_issues(
            covered_constraint_ids=set(),
            known_constraint_ids=known_constraint_ids,
            artifact=script_artifact,
        )
    if not isinstance(checkpoints, list):
        return [
            issue(
                "checkpoint_payload_invalid",
                f"{checkpoint_json_path[2:]} must be a list",
                json_paths=[checkpoint_json_path],
                provenance={
                    "layer": "f4",
                    "source": "authored_check",
                    "check_id": None,
                    "constraint_ids": [],
                    "func": None,
                    "impl_source": "unknown",
                    "args": None,
                    "artifact": script_artifact,
                },
            )
        ]

    view = IntentTGraphView.from_json(tgraph)
    custom_functions, script_issues = _load_custom_functions(script, artifact=script_artifact)
    if script_issues:
        return script_issues

    issues: list[dict[str, Any]] = _checkpoint_metadata_issues(
        checkpoints,
        custom_functions=custom_functions,
        known_constraint_ids=known_constraint_ids,
        checkpoint_json_path=checkpoint_json_path,
    )
    for raw_checkpoint in checkpoints:
        checkpoint = raw_checkpoint if isinstance(raw_checkpoint, dict) else {}
        checkpoint_id = str(checkpoint.get("id") or "unknown_checkpoint")
        func_name = str(checkpoint.get("func") or "").strip()
        args = checkpoint.get("args")
        if not isinstance(args, dict):
            issues.append(
                _checkpoint_issue(
                    checkpoint,
                    "checkpoint_args_invalid",
                    "checkpoint args must be an object",
                    impl_source=_resolve_impl_source(func_name, custom_functions),
                    args=None,
                )
            )
            continue

        fn = SDK_FUNCTIONS.get(func_name) or custom_functions.get(func_name)
        if fn is None:
            issues.append(
                _checkpoint_issue(
                    checkpoint,
                    "checkpoint_function_missing",
                    f"unknown checkpoint function '{func_name}'",
                    impl_source="unknown",
                    args=args,
                )
            )
            continue

        try:
            result = fn(view, **args)
        except Exception as exc:  # noqa: BLE001
            issues.append(
                _checkpoint_issue(
                    checkpoint,
                    "checkpoint_function_runtime_error",
                    f"{func_name} raised {type(exc).__name__}: {exc}",
                    impl_source=_resolve_impl_source(func_name, custom_functions),
                    args=args,
                )
            )
            continue

        normalized, normalize_issues = _normalize_checkpoint_result(
            result,
            checkpoint=checkpoint,
            impl_source=_resolve_impl_source(func_name, custom_functions),
            args=args,
        )
        issues.extend(normalized)
        issues.extend(normalize_issues)

    return issues


def _resolve_checkpoint_payload(kwargs: dict[str, Any]) -> tuple[Any, Any, str, str, Any]:
    if "logical_checkpoints" in kwargs or "logical_validator_script" in kwargs:
        return (
            kwargs.get("logical_checkpoints") or [],
            kwargs.get("logical_validator_script"),
            "$.logical_checkpoints",
            "logical_validator_script",
            kwargs.get("logical_constraints") or [],
        )
    if "physical_checkpoints" in kwargs or "physical_validator_script" in kwargs:
        return (
            kwargs.get("physical_checkpoints") or [],
            kwargs.get("physical_validator_script"),
            "$.physical_checkpoints",
            "physical_validator_script",
            kwargs.get("physical_constraints") or [],
        )
    return [], None, "$.logical_checkpoints", "logical_validator_script", []


def _known_constraint_ids(constraints: Any) -> set[str]:
    known: set[str] = set()
    if not isinstance(constraints, list):
        return known
    for constraint in constraints:
        if not isinstance(constraint, dict):
            continue
        constraint_id = str(constraint.get("id") or "").strip()
        if constraint_id:
            known.add(constraint_id)
    return known


def _checkpoint_metadata_issues(
    checkpoints: list[Any],
    *,
    custom_functions: dict[str, Callable[..., Any]],
    known_constraint_ids: set[str],
    checkpoint_json_path: str,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    covered_constraint_ids: set[str] = set()
    for index, raw_checkpoint in enumerate(checkpoints):
        if not isinstance(raw_checkpoint, dict):
            issues.append(
                issue(
                    "checkpoint_payload_invalid",
                    "checkpoint must be an object",
                    json_paths=[f"{checkpoint_json_path}[{index}]"],
                    provenance={
                        "layer": "f4",
                        "source": "authored_check",
                        "check_id": None,
                        "constraint_ids": [],
                        "func": None,
                        "impl_source": "unknown",
                        "args": None,
                        "artifact": None,
                    },
                )
            )
            continue

        checkpoint = raw_checkpoint
        checkpoint_id = str(checkpoint.get("id") or "unknown_checkpoint")
        func_name = str(checkpoint.get("func") or "").strip()
        for field in ("id", "func", "description", "constraint_ids", "args"):
            if field not in checkpoint:
                issues.append(
                    _checkpoint_issue(
                        checkpoint,
                        "checkpoint_field_missing",
                        f"checkpoint missing required field '{field}'",
                        impl_source=_resolve_impl_source(func_name, custom_functions),
                        args=checkpoint.get("args") if isinstance(checkpoint.get("args"), dict) else None,
                    )
                )

        constraint_ids = checkpoint.get("constraint_ids")
        if not isinstance(constraint_ids, list):
            issues.append(
                _checkpoint_issue(
                    checkpoint,
                    "checkpoint_constraint_ids_invalid",
                    "checkpoint constraint_ids must be a list",
                    impl_source=_resolve_impl_source(func_name, custom_functions),
                    args=checkpoint.get("args") if isinstance(checkpoint.get("args"), dict) else None,
                )
            )
            continue

        normalized_ids = [str(item).strip() for item in constraint_ids if str(item).strip()]
        covered_constraint_ids.update(normalized_ids)
        if known_constraint_ids:
            for constraint_id in normalized_ids:
                if constraint_id not in known_constraint_ids:
                    issues.append(
                        _checkpoint_issue(
                            checkpoint,
                            "checkpoint_constraint_unknown",
                            f"checkpoint references unknown constraint id '{constraint_id}'",
                            impl_source=_resolve_impl_source(func_name, custom_functions),
                            args=checkpoint.get("args") if isinstance(checkpoint.get("args"), dict) else None,
                            constraint_ids=[constraint_id],
                        )
                    )

    issues.extend(
        _missing_coverage_issues(
            covered_constraint_ids=covered_constraint_ids,
            known_constraint_ids=known_constraint_ids,
            artifact=None,
        )
    )
    return issues


def _missing_coverage_issues(
    *,
    covered_constraint_ids: set[str],
    known_constraint_ids: set[str],
    artifact: str | None,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for constraint_id in sorted(known_constraint_ids - covered_constraint_ids):
        issues.append(
            issue(
                "checkpoint_coverage_missing",
                f"缺少覆盖该约束的 checkpoint: {constraint_id}",
                targets=[f"constraint:{constraint_id}"],
                provenance={
                    "layer": "f4",
                    "source": "authored_check",
                    "check_id": None,
                    "constraint_ids": [constraint_id],
                    "func": None,
                    "impl_source": "unknown",
                    "args": None,
                    "artifact": artifact,
                },
            )
        )
    return issues


def _load_custom_functions(script: Any, *, artifact: str) -> tuple[dict[str, Callable[..., Any]], list[dict[str, Any]]]:
    if script is None:
        return {}, []
    if not isinstance(script, str) or not script.strip():
        return {}, []
    try:
        ast.parse(script)
    except SyntaxError as exc:
        return {}, [
            issue(
                "checkpoint_script_syntax_error",
                f"invalid {artifact}: {exc}",
                provenance={
                    "layer": "f4",
                    "source": "authored_check",
                    "check_id": None,
                    "constraint_ids": [],
                    "func": None,
                    "impl_source": "custom",
                    "args": None,
                    "artifact": artifact,
                },
            )
        ]

    safe_globals: dict[str, Any] = {
        "__builtins__": SAFE_BUILTINS,
        **SDK_GLOBALS,
    }
    local_vars: dict[str, Any] = {}
    try:
        exec(script, safe_globals, local_vars)  # noqa: S102
    except Exception as exc:  # noqa: BLE001
        return {}, [
            issue(
                "checkpoint_script_error",
                f"{artifact} execution failed: {exc}",
                provenance={
                    "layer": "f4",
                    "source": "authored_check",
                    "check_id": None,
                    "constraint_ids": [],
                    "func": None,
                    "impl_source": "custom",
                    "args": None,
                    "artifact": artifact,
                },
            )
        ]

    functions: dict[str, Callable[..., Any]] = {}
    for name, value in local_vars.items():
        if callable(value) and not str(name).startswith("_"):
            functions[str(name)] = value
    return functions, []


def _normalize_checkpoint_result(
    result: Any,
    *,
    checkpoint: dict[str, Any],
    impl_source: str,
    args: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    checkpoint_id = str(checkpoint.get("id") or "unknown_checkpoint")
    if result is None:
        return [], []
    if not isinstance(result, list):
        return [], [
            _checkpoint_issue(
                checkpoint,
                "checkpoint_return_invalid",
                "checkpoint function must return a list",
                impl_source=impl_source,
                args=args,
            )
        ]

    normalized: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for item in result:
        if isinstance(item, str):
            normalized.append(
                _checkpoint_issue(
                    checkpoint,
                    "checkpoint_issue",
                    item,
                    impl_source=impl_source,
                    args=args,
                )
            )
            continue
        if not isinstance(item, dict):
            issues.append(
                _checkpoint_issue(
                    checkpoint,
                    "checkpoint_return_invalid",
                    "checkpoint result item must be object or string",
                    impl_source=impl_source,
                    args=args,
                )
            )
            continue
        normalized.append(
            issue(
                str(item.get("code") or "checkpoint_issue"),
                str(item.get("message") or "checkpoint reported an issue"),
                severity=str(item.get("severity") or "error"),
                targets=[str(target) for target in item.get("targets") or [f"checkpoint:{checkpoint_id}"]],
                json_paths=[str(path) for path in item.get("json_paths") or []],
                provenance=_checkpoint_provenance(
                    checkpoint=checkpoint,
                    impl_source=impl_source,
                    args=args,
                ),
            )
        )
    return normalized, issues


def _checkpoint_issue(
    checkpoint: dict[str, Any],
    code: str,
    message: str,
    *,
    impl_source: str,
    args: dict[str, Any] | None,
    constraint_ids: list[str] | None = None,
) -> dict[str, Any]:
    checkpoint_id = str(checkpoint.get("id") or "unknown_checkpoint")
    return issue(
        code,
        message,
        targets=[f"checkpoint:{checkpoint_id}"],
        provenance=_checkpoint_provenance(
            checkpoint=checkpoint,
            impl_source=impl_source,
            args=args,
            constraint_ids=constraint_ids,
        ),
    )


def _checkpoint_provenance(
    *,
    checkpoint: dict[str, Any],
    impl_source: str,
    args: dict[str, Any] | None,
    constraint_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "layer": "f4",
        "source": "authored_check",
        "check_id": str(checkpoint.get("id") or "unknown_checkpoint"),
        "constraint_ids": constraint_ids if constraint_ids is not None else [str(item) for item in checkpoint.get("constraint_ids") or []],
        "func": str(checkpoint.get("func") or "").strip() or None,
        "impl_source": impl_source,
        "args": dict(args) if isinstance(args, dict) else None,
        "artifact": None,
    }


def _resolve_impl_source(func_name: str, custom_functions: dict[str, Callable[..., Any]]) -> str:
    if func_name in SDK_FUNCTIONS:
        return "sdk"
    if func_name in custom_functions:
        return "custom"
    return "unknown"
