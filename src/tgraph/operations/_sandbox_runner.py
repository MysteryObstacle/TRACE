from __future__ import annotations

import ast
import multiprocessing as mp
import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from tgraph.operations._execution_mode import use_inline_execution


@dataclass(frozen=True)
class SandboxWorkerResult:
    payload: dict[str, Any] | None
    timed_out: bool = False


def read_source_file(path: str | Path) -> tuple[str | None, OSError | None]:
    try:
        return Path(path).read_text(encoding="utf-8"), None
    except OSError as exc:
        return None, exc


def parse_source(source: str, *, source_path: str) -> tuple[ast.Module | None, SyntaxError | None]:
    try:
        return ast.parse(source, filename=source_path), None
    except SyntaxError as exc:
        return None, exc


def imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def disallowed_imports(tree: ast.AST, allowed_modules: Mapping[str, Any]) -> list[str]:
    return sorted(module for module in imported_modules(tree) if module not in allowed_modules)


def guarded_import(allowed_modules: Mapping[str, Any], *, file_kind: str) -> Callable[..., Any]:
    def _import(name: str, globals: dict[str, Any] | None = None, locals: dict[str, Any] | None = None, fromlist: tuple[str, ...] = (), level: int = 0) -> Any:
        del globals, locals, fromlist, level
        if name in allowed_modules:
            return allowed_modules[name]
        raise ImportError(f"module '{name}' is not available in {file_kind} files")

    return _import


def run_sandbox_worker(
    *,
    target: Callable[..., None],
    args: tuple[Any, ...],
    timeout_seconds: float,
) -> SandboxWorkerResult:
    if use_inline_execution():
        result_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        worker = threading.Thread(target=target, args=(result_queue, *args), daemon=True)
        worker.start()
        worker.join(timeout_seconds)
        if worker.is_alive():
            return SandboxWorkerResult(payload=None, timed_out=True)
        try:
            return SandboxWorkerResult(payload=result_queue.get_nowait())
        except queue.Empty:
            return SandboxWorkerResult(payload=None)

    context = mp.get_context("spawn")
    result_queue = context.Queue()
    worker = context.Process(target=target, args=(result_queue, *args))
    worker.start()
    payload = _read_subprocess_result(worker, result_queue, timeout_seconds)
    if payload is None and worker.is_alive():
        _terminate_subprocess_worker(worker)
        return SandboxWorkerResult(payload=None, timed_out=True)
    return SandboxWorkerResult(payload=payload)


def _read_subprocess_result(
    worker: mp.Process,
    result_queue: mp.Queue,
    timeout_seconds: float,
) -> dict[str, Any] | None:
    payload_box: dict[str, Any] = {}

    def _reader() -> None:
        try:
            payload_box["payload"] = result_queue.get(timeout=max(timeout_seconds, 0.1) + 5.0)
        except queue.Empty:
            return

    reader = threading.Thread(target=_reader, daemon=True)
    reader.start()
    worker.join(timeout_seconds)
    if worker.is_alive():
        reader.join(timeout=0.1)
    else:
        reader.join(timeout=5.0 if worker.exitcode == 0 else 1.0)
    return payload_box.get("payload")


def _terminate_subprocess_worker(worker: mp.Process) -> None:
    if worker.is_alive():
        worker.terminate()
        worker.join()
