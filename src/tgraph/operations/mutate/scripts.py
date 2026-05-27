from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path
import queue
import threading
from typing import Any

from pydantic import BaseModel, Field

from tgraph.core.graph import TGraph
from tgraph.operations._execution_mode import use_inline_execution
from tgraph.operations.mutate.editor import TGraphEditor
from tgraph.operations.validate.issues import ValidationIssue, validation_issue
from tgraph.operations.validate.policy import ValidationContext, ValidationPolicy
from tgraph.operations.validate.runner import validate_graph
from tgraph.operations.validate.sandbox import ALLOWED_MODULES, SAFE_BUILTINS


class MutationExecutionResult(BaseModel):
    ok: bool
    graph: TGraph | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)
    operations: list[dict[str, Any]] = Field(default_factory=list)


def execute_mutation_file(
    graph: TGraph | dict[str, Any],
    *,
    mutation_path: str | Path,
    timeout_seconds: float = 5.0,
    validate: bool = True,
    validation_policy: ValidationPolicy | None = None,
    validation_context: ValidationContext | None = None,
) -> MutationExecutionResult:
    path = Path(mutation_path)
    source_path = str(path).replace("\\", "/")
    current = graph if isinstance(graph, TGraph) else TGraph.model_validate(graph)
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return _failed(
            _file_issue(
                "mutation.file.read_error",
                f"failed to read mutation file: {exc}",
                source_path=source_path,
            )
        )

    preflight_issue = _preflight(source, source_path=source_path)
    if preflight_issue is not None:
        return _failed(preflight_issue)

    worker_args = (current.model_dump(mode="json"), source, source_path)
    if use_inline_execution():
        result_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        worker = threading.Thread(
            target=_mutation_worker,
            args=(result_queue, *worker_args),
            daemon=True,
        )
        worker.start()
        worker.join(timeout_seconds)
        if worker.is_alive():
            return _failed(
                _file_issue(
                    "mutation.execution.timeout",
                    f"mutation file exceeded timeout of {timeout_seconds} seconds",
                    source_path=source_path,
                    details={"timeout_seconds": timeout_seconds, "scope": "file"},
                )
            )
    else:
        context = mp.get_context("spawn")
        result_queue = context.Queue()
        worker = context.Process(target=_mutation_worker, args=(result_queue, *worker_args))
        worker.start()
        worker.join(timeout_seconds)

        if worker.is_alive():
            worker.terminate()
            worker.join()
            return _failed(
                _file_issue(
                    "mutation.execution.timeout",
                    f"mutation file exceeded timeout of {timeout_seconds} seconds",
                    source_path=source_path,
                    details={"timeout_seconds": timeout_seconds, "scope": "file"},
                )
            )

    try:
        payload = result_queue.get_nowait()
    except queue.Empty:
        return _failed(
            _file_issue(
                "mutation.execution.exception",
                "mutation file exited without a result",
                source_path=source_path,
                details={"scope": "file"},
            )
        )

    issues = [ValidationIssue.model_validate(item) for item in payload.get("issues", [])]
    if issues:
        return MutationExecutionResult(ok=False, issues=issues, operations=payload.get("operations", []))

    candidate = TGraph.model_validate(payload["graph"])
    validation = validate_graph(candidate, validation_policy or ValidationPolicy(levels=["f1", "f2", "f3"]), validation_context) if validate else None
    if validation is not None and not validation.ok:
        return MutationExecutionResult(ok=False, issues=validation.issues, operations=payload.get("operations", []))

    return MutationExecutionResult(ok=True, graph=candidate, operations=payload.get("operations", []))


def _mutation_worker(
    result_queue: mp.Queue[dict[str, Any]],
    graph_payload: dict[str, Any],
    source: str,
    source_path: str,
) -> None:
    try:
        globals_dict = {"__builtins__": {**SAFE_BUILTINS, "__import__": _mutation_import}}
        exec(compile(source, source_path, "exec"), globals_dict, globals_dict)  # noqa: S102
        mutate = globals_dict.get("mutate")
        if not callable(mutate):
            result_queue.put(
                {
                    "issues": [
                        _file_issue(
                            "mutation.file.missing_mutate",
                            "mutation file must define mutate(tgraph)",
                            source_path=source_path,
                        ).model_dump(mode="json")
                    ],
                    "operations": [],
                }
            )
            return

        editor = TGraphEditor(graph_payload)
        mutate(editor)
        result_queue.put({"issues": [], "graph": editor.to_graph().model_dump(mode="json"), "operations": editor.operations})
    except Exception as exc:  # noqa: BLE001
        result_queue.put(
            {
                "issues": [
                    _file_issue(
                        "mutation.execution.exception",
                        f"mutation file failed: {type(exc).__name__}: {exc}",
                        source_path=source_path,
                        details={"scope": "file"},
                    ).model_dump(mode="json")
                ],
                "operations": [],
            }
        )


def _preflight(source: str, *, source_path: str) -> ValidationIssue | None:
    try:
        tree = ast.parse(source, filename=source_path)
    except SyntaxError as exc:
        return _file_issue(
            "mutation.file.syntax_error",
            f"mutation file syntax error: {exc}",
            source_path=source_path,
            details={"line": exc.lineno, "offset": exc.offset},
        )

    disallowed = sorted(module for module in _imported_modules(tree) if module not in ALLOWED_MODULES)
    if disallowed:
        return _file_issue(
            "mutation.file.disallowed_import",
            f"mutation file imports disallowed modules: {disallowed}",
            source_path=source_path,
            details={"modules": disallowed},
        )
    return None


def _mutation_import(name: str, globals: dict[str, Any] | None = None, locals: dict[str, Any] | None = None, fromlist: tuple[str, ...] = (), level: int = 0) -> Any:
    del globals, locals, fromlist, level
    if name in ALLOWED_MODULES:
        return ALLOWED_MODULES[name]
    raise ImportError(f"module '{name}' is not available in mutation files")


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def _file_issue(
    issue_kind: str,
    message: str,
    *,
    source_path: str,
    details: dict[str, Any] | None = None,
) -> ValidationIssue:
    payload = dict(details or {})
    payload.setdefault("mutation_path", source_path)
    return validation_issue(issue_kind, message, location=source_path, details=payload)


def _failed(issue: ValidationIssue) -> MutationExecutionResult:
    return MutationExecutionResult(ok=False, issues=[issue])
