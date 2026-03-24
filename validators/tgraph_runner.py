from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Callable

from app.contracts import ValidationIssue, ValidationReport
from stages.logical.output_schema import CheckpointSpec


ValidatorFn = Callable[..., list[dict[str, Any]]]


def f1_format(tgraph: dict[str, Any], **_: Any) -> list[dict[str, Any]]:
    if 'nodes' not in tgraph or 'edges' not in tgraph:
        return [
            {
                'code': 'format_error',
                'message': 'tgraph must contain nodes and edges keys',
                'severity': 'error',
                'scope': 'topology',
                'targets': [],
                'json_paths': [],
            }
        ]
    return []


BUILTIN_VALIDATORS: dict[str, ValidatorFn] = {
    'f1_format': f1_format,
}


def run_tgraph_checks(
    tgraph: dict[str, Any],
    checkpoints: list[dict[str, Any]],
    artifact_root: str | Path,
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    for item in checkpoints:
        checkpoint = CheckpointSpec.model_validate(item)
        raw_issues = _run_single_checkpoint(tgraph, checkpoint, artifact_root)
        issues.extend(ValidationIssue.model_validate(issue) for issue in raw_issues)

    has_errors = any(issue.severity == 'error' for issue in issues)
    return ValidationReport(ok=not has_errors, issues=issues)


def _run_single_checkpoint(
    tgraph: dict[str, Any],
    checkpoint: CheckpointSpec,
    artifact_root: str | Path,
) -> list[dict[str, Any]]:
    if checkpoint.script_ref:
        validator = _load_script_validator(checkpoint, artifact_root)
    else:
        validator = BUILTIN_VALIDATORS[checkpoint.function_name]
    return validator(tgraph, **checkpoint.input_params)


def _load_script_validator(checkpoint: CheckpointSpec, artifact_root: str | Path) -> ValidatorFn:
    script_path = Path(checkpoint.script_ref or '')
    if not script_path.is_absolute() and not script_path.exists():
        script_path = Path(artifact_root) / script_path

    spec = importlib.util.spec_from_file_location('trace_validator', script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f'Could not load validator script: {script_path}')

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    validator = getattr(module, checkpoint.function_name)
    return validator
