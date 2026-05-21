# TGraph IaC Skill Batch Patch Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repo-local, installable `tgraph-iac` Skill backed by a new TRACE batch patch API, without breaking the current LangChain/LangGraph repair pipeline.

**Architecture:** Add `trace.tools.tgraph.patch` as a sidecar API that applies declarative batch patches to artifact envelopes on candidate copies, then normalizes and validates before commit. Keep `runtime.py`, `transaction.py`, and `BoundTGraphTools` intact for existing stage nodes. Add Skill scripts under `skills/tgraph-iac/` that can run from any cwd by resolving TRACE through `--trace-root`, `TGRAPH_TRACE_ROOT`, `TGRAPH_TRACE_PYTHON`, or the current Python environment.

**Tech Stack:** Python 3.10, Pydantic v2, pytest, existing TRACE `TGraphRuntime`/validators, Codex Skill folder format.

---

## Scope And Guardrails

- Use @superpowers:test-driven-development for implementation.
- Do not delete or rewrite `src/trace/tools/tgraph/transaction.py` in this plan.
- Do not change `src/trace/stages/logical/nodes/repair.py` or `src/trace/stages/physical/nodes/repair.py` in this plan.
- Do not change the current `BoundTGraphTools.tools()` surface in this plan.
- Create the Skill in `D:\Projects\Trace\skills\tgraph-iac` so it can be versioned with the project. A later packaging step may copy it to `C:\Users\78643\.codex\skills\tgraph-iac`.
- Commit steps assume a real Git checkout. The current desktop workspace may not have `.git`; if so, skip commit commands and record that limitation.

## File Structure

Create or modify these files:

- Create: `D:\Projects\Trace\src\trace\tools\tgraph\patch.py`
  - Owns artifact envelope inference, patch schema parsing, graph/checkpoint/validator patch application, diff generation, validation, and JSON-shaped result objects.
- Modify: `D:\Projects\Trace\src\trace\tools\tgraph\__init__.py`
  - Re-export the public patch helpers after tests pass.
- Create: `D:\Projects\Trace\src\trace\tools\tgraph\export.py`
  - Provides a small stable export facade. V1 supports `target="tgraph-json"` and returns `export_error` for unsupported targets.
- Create: `D:\Projects\Trace\tests\unit\tools\tgraph\test_patch_protocol.py`
  - Unit tests for `apply_artifact_patch`, conflict handling, reconnect, checkpoint patching, validator replacement, invalid validation non-commit behavior, and diff shape.
- Create: `D:\Projects\Trace\tests\unit\tools\tgraph\test_export.py`
  - Tests the minimal export facade.
- Create: `D:\Projects\Trace\skills\tgraph-iac\SKILL.md`
- Create: `D:\Projects\Trace\skills\tgraph-iac\agents\openai.yaml`
- Create: `D:\Projects\Trace\skills\tgraph-iac\references\patch-protocol.md`
- Create: `D:\Projects\Trace\skills\tgraph-iac\references\tgraph-ir.md`
- Create: `D:\Projects\Trace\skills\tgraph-iac\references\validation.md`
- Create: `D:\Projects\Trace\skills\tgraph-iac\references\agent-workflows.md`
- Create: `D:\Projects\Trace\skills\tgraph-iac\references\export-targets.md`
- Create: `D:\Projects\Trace\skills\tgraph-iac\scripts\trace_backend.py`
- Create: `D:\Projects\Trace\skills\tgraph-iac\scripts\tgraph_inspect.py`
- Create: `D:\Projects\Trace\skills\tgraph-iac\scripts\tgraph_apply_patch.py`
- Create: `D:\Projects\Trace\skills\tgraph-iac\scripts\tgraph_validate.py`
- Create: `D:\Projects\Trace\skills\tgraph-iac\scripts\tgraph_export.py`
- Create: `D:\Projects\Trace\tests\unit\skills\test_tgraph_iac_trace_backend.py`
- Create: `D:\Projects\Trace\tests\unit\skills\test_tgraph_iac_scripts.py`

---

## Chunk 1: TRACE Batch Patch Core

### Task 1: Patch API Skeleton And Artifact Stage Inference

**Files:**
- Create: `D:\Projects\Trace\src\trace\tools\tgraph\patch.py`
- Create: `D:\Projects\Trace\tests\unit\tools\tgraph\test_patch_protocol.py`

- [ ] **Step 1: Write failing tests for stage inference and empty patch**

Add tests:

```python
from trace.tools.tgraph.patch import apply_artifact_patch, infer_artifact_stage


def test_infer_artifact_stage_logical():
    assert infer_artifact_stage({"tgraph_logical": {"profile": "logical.v1", "nodes": [], "links": []}}) == "logical"


def test_infer_artifact_stage_ambiguous_fails():
    result = apply_artifact_patch(
        {
            "tgraph_logical": {"profile": "logical.v1", "nodes": [], "links": []},
            "tgraph_physical": {"profile": "taal.default.v1", "nodes": [], "links": []},
        },
        {"graph_patch": []},
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "artifact_shape_error"


def test_empty_patch_validates_and_does_not_include_artifact_by_default():
    result = apply_artifact_patch(
        {"tgraph_logical": {"profile": "logical.v1", "nodes": [], "links": []}},
        {"graph_patch": [], "options": {"stage": "logical", "validate": ["f1", "f2", "f3"]}},
    )
    assert result["ok"] is True
    assert result["committed"] is True
    assert result["artifact"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/tools/tgraph/test_patch_protocol.py -q`

Expected: FAIL with `ModuleNotFoundError` or missing functions.

- [ ] **Step 3: Implement minimal skeleton**

In `patch.py`, implement:

```python
from __future__ import annotations

from copy import deepcopy
from typing import Any

from trace.tools.tgraph.runtime import TGraphRuntime
from trace.tools.tgraph.validate import run_default_validators


STAGE_FIELDS = {
    "logical": ("tgraph_logical", "logical_checkpoints", "logical_validator_script"),
    "physical": ("tgraph_physical", "physical_checkpoints", "physical_validator_script"),
}


def infer_artifact_stage(artifact: dict[str, Any]) -> str:
    matches = [stage for stage, (graph_field, _, _) in STAGE_FIELDS.items() if graph_field in artifact]
    if len(matches) == 1:
        return matches[0]
    raise ValueError("artifact stage is ambiguous or missing")


def apply_artifact_patch(
    artifact: dict[str, Any],
    patch: dict[str, Any],
    *,
    stage: str | None = None,
    dry_run: bool | None = None,
    include_artifact: bool | None = None,
) -> dict[str, Any]:
    try:
        selected_stage = stage or patch.get("options", {}).get("stage") or infer_artifact_stage(artifact)
        graph_field, checkpoints_field, validator_field = STAGE_FIELDS[selected_stage]
    except (KeyError, ValueError) as exc:
        return _error_result("artifact_shape_error", str(exc))

    candidate = deepcopy(artifact)
    options = dict(patch.get("options") or {})
    effective_dry_run = bool(options.get("dry_run") if dry_run is None else dry_run)
    effective_include_artifact = bool(options.get("include_artifact") if include_artifact is None else include_artifact)
    levels = options.get("validate") or ["f1", "f2", "f3", "f4"]

    try:
        candidate[graph_field] = TGraphRuntime.from_json(candidate[graph_field]).to_json()
    except Exception as exc:
        return _error_result("artifact_shape_error", str(exc))

    validation_kwargs = {checkpoints_field: candidate.get(checkpoints_field, [])}
    if candidate.get(validator_field) is not None:
        validation_kwargs[validator_field] = candidate.get(validator_field)
    validation = run_default_validators(candidate[graph_field], **validation_kwargs).model_dump(mode="json")

    result = _base_result()
    result["ok"] = validation["ok"]
    result["committed"] = bool(validation["ok"] and not effective_dry_run)
    result["validation"] = validation
    if effective_include_artifact:
        result["artifact"] = candidate
    if not validation["ok"]:
        result["error"] = {"code": "validation_failed", "message": "validation failed"}
    return result
```

Also add `_base_result` and `_error_result` helpers with the result shape from the spec.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/unit/tools/tgraph/test_patch_protocol.py -q`

Expected: PASS for the new skeleton tests.

- [ ] **Step 5: Commit**

```powershell
git add src/trace/tools/tgraph/patch.py tests/unit/tools/tgraph/test_patch_protocol.py
git commit -m "feat: add tgraph patch api skeleton"
```

### Task 2: Graph Patch Operations

**Files:**
- Modify: `D:\Projects\Trace\src\trace\tools\tgraph\patch.py`
- Modify: `D:\Projects\Trace\tests\unit\tools\tgraph\test_patch_protocol.py`

- [ ] **Step 1: Write failing tests for graph operations**

Add tests covering:

```python
def test_ensure_node_creates_and_merges_existing_node(): ...
def test_ensure_link_creates_missing_ports_and_link(): ...
def test_ensure_link_is_idempotent_and_updates_addressing(): ...
def test_ensure_link_conflicts_when_port_already_connected(): ...
def test_ensure_link_reconnect_removes_old_incident_link(): ...
def test_remove_link_keeps_ports(): ...
def test_remove_node_cascade_removes_incident_links(): ...
```

Use small logical artifacts with `validate: ["f1", "f2", "f3"]` so F4 checkpoints do not distract from graph semantics.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/tools/tgraph/test_patch_protocol.py -q`

Expected: FAIL because graph ops are not implemented.

- [ ] **Step 3: Implement graph op dispatch**

In `patch.py`, add private helpers:

```python
def _apply_graph_patch(graph: dict[str, Any], ops: list[dict[str, Any]], diff: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted = []
    rejected = []
    for index, op in enumerate(ops):
        try:
            name = op.get("op")
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
            accepted.append({"section": "graph_patch", "index": index, "op": name})
        except PatchError as exc:
            rejected.append({"section": "graph_patch", "index": index, "op": op.get("op"), "error": exc.to_json()})
            break
    return accepted, rejected
```

Implement `PatchError`, `_node_map`, `_port_owner_map`, `_incident_links`, `_ensure_node`, `_ensure_link`, `_remove_link`, and `_remove_node`.

Important semantics:

- `ensure_node`: create if missing; update only present keys among `type`, `label`, `image`, `flavor`.
- `ensure_link`: endpoint requires `port`; missing port requires `node`; create missing ports on existing nodes.
- `ensure_link`: if target pair already exists, update endpoint `ip/cidr` and do not add duplicate link.
- `ensure_link`: if either endpoint has an incident link to a different endpoint and `reconnect` is not true, raise `PatchError("op_conflict", ...)`.
- `ensure_link`: if `reconnect=true`, remove old incident links before adding target link.
- Normalize after all ops with `TGraphRuntime.from_json(graph).to_json()`.

- [ ] **Step 4: Wire graph op dispatch into `apply_artifact_patch`**

Before validation, call `_apply_graph_patch` on `candidate[graph_field]`. If any rejected op exists, return `ok=false`, `committed=false`, `error.code` from the first rejected op, and do not validate.

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/unit/tools/tgraph/test_patch_protocol.py -q`

Expected: PASS.

- [ ] **Step 6: Run existing TGraph tests to confirm no regression**

Run: `python -m pytest tests/unit/tools/tgraph -q`

Expected: PASS. Existing transaction and BoundTGraphTools tests must still pass.

- [ ] **Step 7: Commit**

```powershell
git add src/trace/tools/tgraph/patch.py tests/unit/tools/tgraph/test_patch_protocol.py
git commit -m "feat: add declarative tgraph graph patch ops"
```

### Task 3: Checkpoint, Validator, Diff, And Validation Commit Semantics

**Files:**
- Modify: `D:\Projects\Trace\src\trace\tools\tgraph\patch.py`
- Modify: `D:\Projects\Trace\tests\unit\tools\tgraph\test_patch_protocol.py`

- [ ] **Step 1: Write failing tests**

Add tests:

```python
def test_ensure_checkpoint_creates_and_merges_existing_checkpoint(): ...
def test_ensure_checkpoint_requires_id_and_func_for_new_checkpoint(): ...
def test_remove_checkpoint_removes_by_id(): ...
def test_replace_script_updates_validator_script(): ...
def test_validation_failure_returns_diff_but_committed_false(): ...
def test_include_artifact_returns_candidate_artifact(): ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/tools/tgraph/test_patch_protocol.py -q`

Expected: FAIL for missing checkpoint/validator behavior.

- [ ] **Step 3: Implement checkpoint ops**

Add:

```python
def _apply_checkpoint_patch(checkpoints: list[dict[str, Any]], ops: list[dict[str, Any]], diff: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ...


def _ensure_checkpoint(checkpoints: list[dict[str, Any]], op: dict[str, Any], diff: dict[str, Any]) -> None:
    ...


def _remove_checkpoint(checkpoints: list[dict[str, Any]], op: dict[str, Any], diff: dict[str, Any]) -> None:
    ...
```

Rules:

- New checkpoint requires non-empty `id` and `func`.
- Existing checkpoint merges supplied fields only.
- Allowed merge fields: `func`, `description`, `constraint_ids`, `args`.

- [ ] **Step 4: Implement validator patch**

Add:

```python
def _apply_validator_patch(current_script: str | None, validator_patch: dict[str, Any] | None, diff: dict[str, Any]) -> str | None:
    if validator_patch is None:
        return current_script
    if validator_patch.get("op") != "replace_script":
        raise PatchError("patch_schema_error", "unknown validator_patch op")
    diff["validator_script_replaced"] = True
    return validator_patch.get("script")
```

- [ ] **Step 5: Implement full diff and non-commit validation behavior**

Initialize diff with all keys from the spec. Ensure:

- `ok=false` and `committed=false` when validation fails.
- `accepted_ops` lists candidate-applied ops even when validation fails.
- `artifact` appears only when requested.
- `error.code == "validation_failed"` when validation fails.

- [ ] **Step 6: Run focused and existing tests**

Run:

```powershell
python -m pytest tests/unit/tools/tgraph/test_patch_protocol.py -q
python -m pytest tests/unit/tools/tgraph -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/trace/tools/tgraph/patch.py tests/unit/tools/tgraph/test_patch_protocol.py
git commit -m "feat: add artifact-level tgraph patch ops"
```

### Task 4: Export Facade And Public Package Exports

**Files:**
- Create: `D:\Projects\Trace\src\trace\tools\tgraph\export.py`
- Create: `D:\Projects\Trace\tests\unit\tools\tgraph\test_export.py`
- Modify: `D:\Projects\Trace\src\trace\tools\tgraph\__init__.py`

- [ ] **Step 1: Write failing export tests**

```python
from trace.tools.tgraph.export import export_artifact


def test_export_tgraph_json_returns_normalized_graph():
    artifact = {"tgraph_logical": {"profile": "logical.v1", "nodes": [], "links": []}}
    result = export_artifact(artifact, target="tgraph-json", stage="logical")
    assert result["ok"] is True
    assert result["files"][0]["path"] == "tgraph.json"


def test_export_unsupported_target_returns_export_error():
    result = export_artifact({"tgraph_logical": {"profile": "logical.v1", "nodes": [], "links": []}}, target="terraform", stage="logical")
    assert result["ok"] is False
    assert result["error"]["code"] == "export_error"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/tools/tgraph/test_export.py -q`

Expected: FAIL because `export.py` does not exist.

- [ ] **Step 3: Implement minimal export facade**

In `export.py`, implement:

```python
from __future__ import annotations

import json
from typing import Any

from trace.tools.tgraph.patch import STAGE_FIELDS, infer_artifact_stage
from trace.tools.tgraph.runtime import TGraphRuntime


def export_artifact(artifact: dict[str, Any], *, target: str, stage: str | None = None) -> dict[str, Any]:
    selected_stage = stage or infer_artifact_stage(artifact)
    graph_field, _, _ = STAGE_FIELDS[selected_stage]
    if target != "tgraph-json":
        return {"ok": False, "files": [], "error": {"code": "export_error", "message": f"unsupported export target: {target}"}}
    graph = TGraphRuntime.from_json(artifact[graph_field]).to_json()
    return {
        "ok": True,
        "files": [{"path": "tgraph.json", "content": json.dumps(graph, indent=2, ensure_ascii=False)}],
        "error": None,
    }
```

- [ ] **Step 4: Export public helpers in `__init__.py`**

Add imports for `apply_artifact_patch`, `infer_artifact_stage`, and `export_artifact`. Preserve existing exports.

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/unit/tools/tgraph/test_export.py -q
python -m pytest tests/unit/tools/tgraph -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/trace/tools/tgraph/export.py src/trace/tools/tgraph/__init__.py tests/unit/tools/tgraph/test_export.py
git commit -m "feat: add tgraph export facade"
```

---

## Chunk 2: Skill Scripts

### Task 5: Initialize Repo-Local Skill Skeleton

**Files:**
- Create: `D:\Projects\Trace\skills\tgraph-iac\SKILL.md`
- Create: `D:\Projects\Trace\skills\tgraph-iac\agents\openai.yaml`
- Create directories: `D:\Projects\Trace\skills\tgraph-iac\scripts`, `D:\Projects\Trace\skills\tgraph-iac\references`

- [ ] **Step 1: Initialize the Skill directory**

Run:

```powershell
python C:\Users\78643\.codex\skills\.system\skill-creator\scripts\init_skill.py tgraph-iac --path D:\Projects\Trace\skills --resources scripts,references --interface display_name="TGraph IaC" --interface short_description="Generate, repair, validate, and export TGraph IaC artifacts." --interface default_prompt="Use TGraph as an IaC intermediate representation. Inspect artifacts, apply declarative batch patches, validate, and export."
```

Expected: Creates `D:\Projects\Trace\skills\tgraph-iac`.

- [ ] **Step 2: Remove placeholder resources if generated**

Delete only placeholder example files created by `init_skill.py`; keep required directories.

- [ ] **Step 3: Commit**

```powershell
git add skills/tgraph-iac
git commit -m "chore: initialize tgraph iac skill"
```

### Task 6: TRACE Backend Resolver Script

**Files:**
- Create: `D:\Projects\Trace\skills\tgraph-iac\scripts\trace_backend.py`
- Create: `D:\Projects\Trace\tests\unit\skills\test_tgraph_iac_trace_backend.py`

- [ ] **Step 1: Write failing resolver tests**

Use `importlib.util.spec_from_file_location` to load the script module from its path. Add tests:

```python
def test_resolve_trace_root_inserts_src_and_imports_project_trace(tmp_path, monkeypatch): ...
def test_resolve_backend_reports_missing_trace_root(tmp_path): ...
def test_build_base_parser_accepts_trace_root_argument(): ...
```

The first test should pass `trace_root=Path.cwd()` when running from `D:\Projects\Trace` and assert imported `trace.tools.tgraph.__file__` contains `src`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/skills/test_tgraph_iac_trace_backend.py -q`

Expected: FAIL because resolver script does not exist.

- [ ] **Step 3: Implement `trace_backend.py`**

Implement:

```python
from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


class BackendResolutionError(Exception):
    pass


def add_trace_backend_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--trace-root", default=None)
    parser.add_argument("--trace-python", default=None)


def resolve_trace_backend(trace_root: str | None = None, trace_python: str | None = None):
    root = trace_root or os.environ.get("TGRAPH_TRACE_ROOT")
    python = trace_python or os.environ.get("TGRAPH_TRACE_PYTHON")
    if python:
        return {"mode": "python", "python": python}
    if root:
        src = Path(root).resolve() / "src"
        if not src.exists():
            raise BackendResolutionError(f"TRACE src directory not found: {src}")
        sys.path.insert(0, str(src))
    module = importlib.import_module("trace.tools.tgraph")
    module_file = Path(getattr(module, "__file__", "")).resolve()
    if root and Path(root).resolve() not in module_file.parents:
        raise BackendResolutionError(f"loaded trace module outside TRACE root: {module_file}")
    return {"mode": "inprocess", "module": module}


def print_json(payload: dict[str, Any], exit_code: int = 0) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(exit_code)
```

Do not implement subprocess delegation for `TGRAPH_TRACE_PYTHON` yet unless the script needs it in later tasks; returning mode metadata is enough for tests.

- [ ] **Step 4: Run resolver tests**

Run: `python -m pytest tests/unit/skills/test_tgraph_iac_trace_backend.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add skills/tgraph-iac/scripts/trace_backend.py tests/unit/skills/test_tgraph_iac_trace_backend.py
git commit -m "feat: add tgraph skill backend resolver"
```

### Task 7: Apply, Validate, Inspect, And Export Scripts

**Files:**
- Create: `D:\Projects\Trace\skills\tgraph-iac\scripts\tgraph_apply_patch.py`
- Create: `D:\Projects\Trace\skills\tgraph-iac\scripts\tgraph_validate.py`
- Create: `D:\Projects\Trace\skills\tgraph-iac\scripts\tgraph_inspect.py`
- Create: `D:\Projects\Trace\skills\tgraph-iac\scripts\tgraph_export.py`
- Create: `D:\Projects\Trace\tests\unit\skills\test_tgraph_iac_scripts.py`

- [ ] **Step 1: Write failing script tests**

Use `subprocess.run` with `sys.executable` and temporary artifact files. Add tests:

```python
def test_apply_patch_script_writes_output_from_arbitrary_cwd(tmp_path): ...
def test_apply_patch_script_dry_run_does_not_write_output(tmp_path): ...
def test_validate_script_outputs_validation_report(tmp_path): ...
def test_inspect_script_outputs_topology(tmp_path): ...
def test_export_script_writes_tgraph_json_file(tmp_path): ...
```

Each subprocess call should include `--trace-root D:\Projects\Trace`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/skills/test_tgraph_iac_scripts.py -q`

Expected: FAIL because scripts do not exist.

- [ ] **Step 3: Implement `tgraph_apply_patch.py`**

Behavior:

- Parse `--artifact`, `--patch`, `--stage`, `--out`, `--dry-run`, `--include-artifact`, and backend args.
- Resolve backend before importing TRACE patch API.
- Load JSON files.
- Call `trace.tools.tgraph.patch.apply_artifact_patch`.
- If `result["committed"]` and `--out` is provided, write `result["artifact"]` if present, otherwise call again with `include_artifact=True` or use an internal returned candidate. Prefer adding an internal `include_artifact=True` call for file writing only, while stdout honors the user's include choice.
- Print JSON result to stdout.

- [ ] **Step 4: Implement `tgraph_validate.py`**

Behavior:

- Parse `--artifact`, `--stage`, `--levels`, and backend args.
- Resolve backend.
- Load artifact, select graph/checkpoints/script by stage.
- Call `run_default_validators`.
- Print report JSON.

- [ ] **Step 5: Implement `tgraph_inspect.py`**

Support V1 queries:

- `--query topology`
- `--query node --id <node_id>`
- `--query links --node <node_id>`
- `--query checkpoints --text <text>`

Use `TGraphRuntime` and simple checkpoint text matching. Keep it deterministic and small.

- [ ] **Step 6: Implement `tgraph_export.py`**

Behavior:

- Parse `--artifact`, `--target`, `--stage`, `--out`, and backend args.
- Call `export_artifact`.
- If result ok and `--out` supplied, create the output directory and write returned file entries.
- Print result JSON with file contents omitted when files are written to disk. Include file paths and `ok`.

- [ ] **Step 7: Run script tests**

Run: `python -m pytest tests/unit/skills/test_tgraph_iac_scripts.py -q`

Expected: PASS.

- [ ] **Step 8: Run all relevant tests**

Run:

```powershell
python -m pytest tests/unit/tools/tgraph tests/unit/skills -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add skills/tgraph-iac/scripts tests/unit/skills
git commit -m "feat: add tgraph iac skill scripts"
```

---

## Chunk 3: Skill Documentation And Verification

### Task 8: Write Skill Instructions And References

**Files:**
- Modify: `D:\Projects\Trace\skills\tgraph-iac\SKILL.md`
- Modify: `D:\Projects\Trace\skills\tgraph-iac\agents\openai.yaml`
- Create/modify: all files under `D:\Projects\Trace\skills\tgraph-iac\references\`

- [ ] **Step 1: Write `SKILL.md`**

Frontmatter:

```yaml
---
name: tgraph-iac
description: Generate, inspect, repair, validate, and export TGraph-based Infrastructure-as-Code artifacts. Use when Codex needs to work with TRACE/TGraph IR, apply declarative batch patches to logical or physical topology artifacts, validate F1-F4 constraints, repair authored checkpoints or validator scripts, or export validated TGraph artifacts to IaC-oriented outputs.
---
```

Body must include:

- Resolve TRACE backend first.
- Use `tgraph_inspect.py` for focused context.
- Use `tgraph_apply_patch.py` as the only write path.
- Validate after patches.
- Export only after validation passes.
- Load `references/patch-protocol.md` before authoring non-trivial patches.
- Load `references/validation.md` when interpreting F1-F4 issues.
- Load `references/export-targets.md` before export.

- [ ] **Step 2: Write `references/patch-protocol.md`**

Include:

- Patch envelope.
- `ensure_node`, `ensure_link`, `remove_link`, `remove_node`.
- `ensure_checkpoint`, `remove_checkpoint`.
- `replace_script`.
- Result shape and error model.
- A compact repair example.

- [ ] **Step 3: Write `references/tgraph-ir.md`**

Include:

- Logical and physical envelope fields.
- TGraphJSON shape.
- Supported node types.
- Port and link canonical rules.
- Note that link ids are normalized.

- [ ] **Step 4: Write `references/validation.md`**

Include:

- F1 format, F2 schema, F3 consistency, F4 intent.
- How to decide graph vs checkpoint vs validator-script repair.
- Rule: do not edit validator script until issue clearly points to check logic.

- [ ] **Step 5: Write `references/agent-workflows.md`**

Include:

- Generate workflow.
- Repair workflow.
- Export workflow.
- Dry-run guidance.

- [ ] **Step 6: Write `references/export-targets.md`**

Include:

- V1 supports `tgraph-json`.
- Terraform/OpenTofu/Ansible are future targets unless implemented in a later plan.
- Unsupported targets return `export_error`.

- [ ] **Step 7: Regenerate or verify `agents/openai.yaml`**

Run:

```powershell
python C:\Users\78643\.codex\skills\.system\skill-creator\scripts\generate_openai_yaml.py D:\Projects\Trace\skills\tgraph-iac --interface display_name="TGraph IaC" --interface short_description="Generate, repair, validate, and export TGraph IaC artifacts." --interface default_prompt="Use TGraph as an IaC intermediate representation. Inspect artifacts, apply declarative batch patches, validate, and export."
```

- [ ] **Step 8: Commit**

```powershell
git add skills/tgraph-iac/SKILL.md skills/tgraph-iac/agents/openai.yaml skills/tgraph-iac/references
git commit -m "docs: document tgraph iac skill workflow"
```

### Task 9: Skill Validation And Workflow Smoke Test

**Files:**
- Modify only if validation exposes issues.

- [ ] **Step 1: Validate the Skill folder**

Run:

```powershell
python C:\Users\78643\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\Projects\Trace\skills\tgraph-iac
```

Expected: PASS.

- [ ] **Step 2: Run targeted test suite**

Run:

```powershell
python -m pytest tests/unit/tools/tgraph tests/unit/skills -q
```

Expected: PASS.

- [ ] **Step 3: Run existing pipeline-safe tests**

Run:

```powershell
python -m pytest tests/unit/stages tests/integration tests/e2e -q
```

Expected: PASS. This confirms current LangChain/LangGraph paths still work.

- [ ] **Step 4: Run a manual script smoke test from a different cwd**

Create temp artifact and patch files under a temp directory. Then from another cwd:

```powershell
python D:\Projects\Trace\skills\tgraph-iac\scripts\tgraph_apply_patch.py --trace-root D:\Projects\Trace --artifact <temp>\artifact.json --patch <temp>\patch.json --stage logical --out <temp>\artifact.out.json
python D:\Projects\Trace\skills\tgraph-iac\scripts\tgraph_validate.py --trace-root D:\Projects\Trace --artifact <temp>\artifact.out.json --stage logical --levels f1,f2,f3
```

Expected: both commands print JSON with `ok: true`.

- [ ] **Step 5: Forward-test with a fresh agent only if explicitly approved**

Because this environment requires explicit user permission before spawning subagents, ask the user before running the forward-test. Proposed prompt:

```text
Use $tgraph-iac at D:\Projects\Trace\skills\tgraph-iac to repair this artifact: a logical graph with nodes A and B, a checkpoint requiring connect_nodes(A,B), and no link. Use the Skill workflow and produce the patch plus validation result.
```

- [ ] **Step 6: Commit validation fixes**

```powershell
git add skills/tgraph-iac tests src/trace/tools/tgraph
git commit -m "test: verify tgraph iac skill workflow"
```

### Task 10: Final Compatibility Check

**Files:**
- No expected changes.

- [ ] **Step 1: Search for old transaction callers**

Run:

```powershell
rg -n "begin_transaction|TGraphTransaction|BoundTGraphTools|add_link\\(|update_link\\(" src tests
```

Expected: Existing callers remain; this plan does not migrate them.

- [ ] **Step 2: Confirm no current repair nodes were modified**

Run:

```powershell
git diff -- src/trace/stages/logical/nodes/repair.py src/trace/stages/physical/nodes/repair.py src/trace/tools/tgraph/transaction.py src/trace/tools/tgraph/protocol.py
```

Expected: empty diff for those files.

- [ ] **Step 3: Run full tests if environment allows**

Run:

```powershell
python -m pytest -q
```

Expected: PASS.

- [ ] **Step 4: Document any skipped verification**

If the workspace is not a Git checkout or dependencies are missing, record skipped commit/test steps in the final implementation report.

