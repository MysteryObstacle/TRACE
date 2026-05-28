from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, Field

from tgraph.core.graph import TGraph
from tgraph.operations._sandbox_runner import (
    disallowed_imports,
    guarded_import,
    parse_source,
    read_source_file,
    run_sandbox_worker,
)
from tgraph.operations.validate.constraint_files import ConstraintFact
from tgraph.operations.validate.issues import ValidationIssue, validation_issue
from tgraph.operations.validate.sandbox import ALLOWED_MODULES, SAFE_BUILTINS
from tgraph.operations.validate.view import TGraphView


class CheckpointFileExecutionResult(BaseModel):
    ok: bool
    issues: list[ValidationIssue] = Field(default_factory=list)

    @classmethod
    def from_issues(cls, issues: list[ValidationIssue]) -> "CheckpointFileExecutionResult":
        return cls(ok=not any(issue.severity == "error" for issue in issues), issues=issues)


def execute_checkpoint_file(
    graph: TGraph | dict[str, Any],
    *,
    constraints: Mapping[str, ConstraintFact],
    checkpoint_path: str | Path,
    references: Mapping[str, TGraph | dict[str, Any]] | None = None,
    timeout_seconds: float = 5.0,
) -> CheckpointFileExecutionResult:
    path = Path(checkpoint_path)
    source_path = _source_path(path)
    current = graph if isinstance(graph, TGraph) else TGraph.model_validate(graph)
    source, read_error = read_source_file(path)
    if read_error is not None or source is None:
        return CheckpointFileExecutionResult.from_issues(
            [
                _file_issue(
                    "checkpoint.file.read_error",
                    f"failed to read checkpoint file: {read_error}",
                    source_path=source_path,
                )
            ]
        )

    preflight = _preflight(source, constraints=constraints, source_path=source_path)
    if preflight.hard_stop:
        return CheckpointFileExecutionResult.from_issues(preflight.issues)

    executable_constraints = {
        constraint_id: fact
        for constraint_id, fact in constraints.items()
        if f"check_{constraint_id}" in preflight.function_names
    }
    if not executable_constraints:
        return CheckpointFileExecutionResult.from_issues(preflight.issues)

    worker_args = (
        current.model_dump(mode="json"),
        {name: _dump_graph(ref) for name, ref in (references or {}).items()},
        source,
        source_path,
        {constraint_id: fact.model_dump(mode="json") for constraint_id, fact in executable_constraints.items()},
    )
    worker_result = run_sandbox_worker(
        target=_checkpoint_file_worker,
        args=worker_args,
        timeout_seconds=timeout_seconds,
    )
    payload = worker_result.payload
    if worker_result.timed_out:
        return CheckpointFileExecutionResult.from_issues(
            [
                _file_issue(
                    "checkpoint.execution.timeout",
                    f"checkpoint file exceeded timeout of {timeout_seconds} seconds",
                    source_path=source_path,
                    details={"timeout_seconds": timeout_seconds, "scope": "file"},
                )
            ]
        )
    if payload is None:
        return CheckpointFileExecutionResult.from_issues(
            [
                _file_issue(
                    "checkpoint.execution.exception",
                    "checkpoint file exited without a result",
                    source_path=source_path,
                    details={"scope": "file"},
                )
            ]
        )

    issues = [ValidationIssue.model_validate(item) for item in payload.get("issues", [])]
    return CheckpointFileExecutionResult.from_issues([*preflight.issues, *issues])


class _PreflightResult(BaseModel):
    hard_stop: bool = False
    function_names: set[str] = Field(default_factory=set)
    issues: list[ValidationIssue] = Field(default_factory=list)


def _preflight(source: str, *, constraints: Mapping[str, ConstraintFact], source_path: str) -> _PreflightResult:
    try:
        tree, syntax_error = parse_source(source, source_path=source_path)
        if syntax_error is not None or tree is None:
            raise syntax_error
    except SyntaxError as exc:
        return _PreflightResult(
            hard_stop=True,
            issues=[
                _file_issue(
                    "checkpoint.file.syntax_error",
                    f"checkpoint file syntax error: {exc}",
                    source_path=source_path,
                    details={"line": exc.lineno, "offset": exc.offset},
                )
            ],
        )

    issues: list[ValidationIssue] = []
    disallowed = disallowed_imports(tree, ALLOWED_MODULES)
    if disallowed:
        return _PreflightResult(
            hard_stop=True,
            issues=[
                _file_issue(
                    "checkpoint.file.disallowed_import",
                    f"checkpoint file imports disallowed modules: {disallowed}",
                    source_path=source_path,
                    details={"modules": disallowed},
                )
            ],
        )

    function_names: list[str] = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("check_")
    ]
    duplicates = sorted({name for name in function_names if function_names.count(name) > 1})
    if duplicates:
        return _PreflightResult(
            hard_stop=True,
            issues=[
                _file_issue(
                    "checkpoint.file.duplicate_function",
                    f"checkpoint file defines duplicate functions: {duplicates}",
                    source_path=source_path,
                    details={"functions": duplicates},
                )
            ],
        )

    available = set(function_names)
    expected = {f"check_{constraint_id}" for constraint_id in constraints}
    for missing in sorted(expected - available):
        constraint_id = missing.removeprefix("check_")
        fact = constraints[constraint_id]
        issues.append(
            _checkpoint_issue(
                "checkpoint.coverage.missing_function",
                f"missing checkpoint function: {missing}",
                source_path=source_path,
                constraint_id=constraint_id,
                fact=fact,
                function_name=missing,
            )
        )

    for orphan in sorted(available - expected):
        issues.append(
            _file_issue(
                "checkpoint.coverage.orphan_function",
                f"checkpoint function has no matching constraint: {orphan}",
                source_path=source_path,
                location=f"{source_path}.{orphan}",
                details={"checkpoint_function": orphan},
            )
        )

    return _PreflightResult(function_names=available, issues=issues)


def _checkpoint_file_worker(
    result_queue: mp.Queue[dict[str, Any]],
    graph_payload: dict[str, Any],
    reference_payloads: dict[str, dict[str, Any]],
    source: str,
    source_path: str,
    constraint_payloads: dict[str, dict[str, Any]],
) -> None:
    issues: list[dict[str, Any]] = []
    try:
        globals_dict = {
            "__builtins__": {**SAFE_BUILTINS, "__import__": guarded_import(ALLOWED_MODULES, file_kind="checkpoint")},
        }
        exec(compile(source, source_path, "exec"), globals_dict, globals_dict)  # noqa: S102
        tgraph = TGraphView(graph_payload, references=reference_payloads)

        for constraint_id, fact_payload in constraint_payloads.items():
            fact = ConstraintFact.model_validate(fact_payload)
            function_name = f"check_{constraint_id}"
            fn = globals_dict.get(function_name)
            if not callable(fn):
                continue
            try:
                result = fn(tgraph)
            except Exception as exc:  # noqa: BLE001
                issues.append(
                    _checkpoint_issue(
                        "checkpoint.execution.exception",
                        f"{function_name} raised {type(exc).__name__}: {exc}",
                        source_path=source_path,
                        constraint_id=constraint_id,
                        fact=fact,
                        function_name=function_name,
                    ).model_dump(mode="json")
                )
                continue
            issues.extend(
                issue.model_dump(mode="json")
                for issue in _normalize_checkpoint_result(
                    result,
                    source_path=source_path,
                    constraint_id=constraint_id,
                    fact=fact,
                    function_name=function_name,
                )
            )
    except Exception as exc:  # noqa: BLE001
        issues.append(
            _file_issue(
                "checkpoint.execution.exception",
                f"checkpoint file failed: {type(exc).__name__}: {exc}",
                source_path=source_path,
                details={"scope": "file"},
            ).model_dump(mode="json")
        )
    result_queue.put({"issues": issues})


def _normalize_checkpoint_result(
    result: Any,
    *,
    source_path: str,
    constraint_id: str,
    fact: ConstraintFact,
    function_name: str,
) -> list[ValidationIssue]:
    if result is None:
        return []

    items = result if isinstance(result, list) else [result]
    issues: list[ValidationIssue] = []
    for item in items:
        if isinstance(item, ValidationIssue):
            payload = item.model_dump(mode="json")
        elif isinstance(item, dict):
            payload = dict(item)
        else:
            issues.append(
                _checkpoint_issue(
                    "checkpoint.return.invalid",
                    "checkpoint function must return issue dictionaries or ValidationIssue objects",
                    source_path=source_path,
                    constraint_id=constraint_id,
                    fact=fact,
                    function_name=function_name,
                )
            )
            continue

        details = dict(payload.get("details") or {})
        _enrich_details(details, source_path=source_path, constraint_id=constraint_id, fact=fact, function_name=function_name)
        payload["details"] = details
        payload.setdefault("location", f"{source_path}.{function_name}")
        try:
            issues.append(ValidationIssue.model_validate(payload))
        except Exception:  # noqa: BLE001
            issues.append(
                _checkpoint_issue(
                    "checkpoint.return.invalid",
                    "checkpoint function returned an invalid issue shape",
                    source_path=source_path,
                    constraint_id=constraint_id,
                    fact=fact,
                    function_name=function_name,
                )
            )
    return issues


def _checkpoint_issue(
    issue_kind: str,
    message: str,
    *,
    source_path: str,
    constraint_id: str,
    fact: ConstraintFact,
    function_name: str,
) -> ValidationIssue:
    details: dict[str, Any] = {}
    _enrich_details(details, source_path=source_path, constraint_id=constraint_id, fact=fact, function_name=function_name)
    return validation_issue(
        issue_kind,
        message,
        location=f"{source_path}.{function_name}",
        details=details,
    )


def _file_issue(
    issue_kind: str,
    message: str,
    *,
    source_path: str,
    location: str | None = None,
    details: dict[str, Any] | None = None,
) -> ValidationIssue:
    payload = dict(details or {})
    payload.setdefault("checkpoint_path", source_path)
    return validation_issue(issue_kind, message, location=location or source_path, details=payload)


def _enrich_details(
    details: dict[str, Any],
    *,
    source_path: str,
    constraint_id: str,
    fact: ConstraintFact,
    function_name: str,
) -> None:
    details.setdefault("constraint_id", constraint_id)
    details.setdefault("fact_kind", fact.kind)
    details.setdefault("statement", fact.statement)
    details.setdefault("checkpoint_function", function_name)
    details.setdefault("checkpoint_path", source_path)


def _dump_graph(graph: TGraph | dict[str, Any]) -> dict[str, Any]:
    current = graph if isinstance(graph, TGraph) else TGraph.model_validate(graph)
    return current.model_dump(mode="json")


def _source_path(path: Path) -> str:
    return str(path).replace("\\", "/")
