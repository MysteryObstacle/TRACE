# Stage Package Layout Refactor Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure each stage package so the subgraph entrypoint lives in `__init__.py`, each LangGraph node lives in its own `nodes/*.py`, and all repository imports point at the new package-root stage APIs.

**Architecture:** Keep `schemas.py`, `state.py`, and `prompts/` in each stage package. Move node functions and stage-local prompt invocation logic into `nodes/*.py`, assemble each subgraph in the package `__init__.py`, and delete the old flat files (`subgraph.py`, `author.py`, `builder.py`, `repair.py`, `validator.py`, `prepare.py`, `context.py`) once all imports are updated.

**Tech Stack:** Python 3.11, LangGraph, pytest

---

## Chunk 1: Package-Root Stage Entrypoints

### Task 1: Add a failing import contract test for package-root stage APIs

**Files:**
- Create: `d:/Projects/Trace/tests/unit/stages/test_stage_package_exports.py`

- [ ] **Step 1: Write the failing test**

```python
from trace.stages.ground import run_ground_stage
from trace.stages.logical import run_logical_stage
from trace.stages.physical import run_physical_stage


def test_stage_packages_export_run_functions():
    assert callable(run_ground_stage)
    assert callable(run_logical_stage)
    assert callable(run_physical_stage)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/stages/test_stage_package_exports.py -q`
Expected: FAIL because package `__init__.py` files do not export these functions yet.

## Chunk 2: Ground Stage Restructure

### Task 2: Move ground stage node logic into `nodes/` and build graph in `__init__.py`

**Files:**
- Create: `d:/Projects/Trace/src/trace/stages/ground/nodes/__init__.py`
- Create: `d:/Projects/Trace/src/trace/stages/ground/nodes/prepare.py`
- Create: `d:/Projects/Trace/src/trace/stages/ground/nodes/author.py`
- Create: `d:/Projects/Trace/src/trace/stages/ground/nodes/evaluator.py`
- Create: `d:/Projects/Trace/src/trace/stages/ground/nodes/finalize.py`
- Modify: `d:/Projects/Trace/src/trace/stages/ground/__init__.py`
- Delete: `d:/Projects/Trace/src/trace/stages/ground/subgraph.py`
- Delete: `d:/Projects/Trace/src/trace/stages/ground/author.py`
- Delete: `d:/Projects/Trace/src/trace/stages/ground/evaluator.py`
- Delete: `d:/Projects/Trace/src/trace/stages/ground/context.py`
- Modify: `d:/Projects/Trace/tests/integration/test_ground_stage.py`

- [ ] **Step 1: Update the integration test to import from `trace.stages.ground`**
- [ ] **Step 2: Run `pytest tests/integration/test_ground_stage.py -q` and confirm it fails**
- [ ] **Step 3: Move ground node logic into `nodes/*.py` and assemble the graph in `ground/__init__.py`**
- [ ] **Step 4: Run `pytest tests/integration/test_ground_stage.py -q` and confirm it passes**

## Chunk 3: Logical and Physical Stage Restructure

### Task 3: Move logical and physical stage node logic into `nodes/` and remove the flat stage modules

**Files:**
- Create: `d:/Projects/Trace/src/trace/stages/logical/nodes/__init__.py`
- Create: `d:/Projects/Trace/src/trace/stages/logical/nodes/prepare.py`
- Create: `d:/Projects/Trace/src/trace/stages/logical/nodes/author.py`
- Create: `d:/Projects/Trace/src/trace/stages/logical/nodes/builder.py`
- Create: `d:/Projects/Trace/src/trace/stages/logical/nodes/validator.py`
- Create: `d:/Projects/Trace/src/trace/stages/logical/nodes/repair.py`
- Create: `d:/Projects/Trace/src/trace/stages/logical/nodes/finalize.py`
- Create: `d:/Projects/Trace/src/trace/stages/physical/nodes/__init__.py`
- Create: `d:/Projects/Trace/src/trace/stages/physical/nodes/prepare.py`
- Create: `d:/Projects/Trace/src/trace/stages/physical/nodes/author.py`
- Create: `d:/Projects/Trace/src/trace/stages/physical/nodes/builder.py`
- Create: `d:/Projects/Trace/src/trace/stages/physical/nodes/validator.py`
- Create: `d:/Projects/Trace/src/trace/stages/physical/nodes/repair.py`
- Create: `d:/Projects/Trace/src/trace/stages/physical/nodes/finalize.py`
- Modify: `d:/Projects/Trace/src/trace/stages/logical/__init__.py`
- Modify: `d:/Projects/Trace/src/trace/stages/physical/__init__.py`
- Delete: `d:/Projects/Trace/src/trace/stages/logical/subgraph.py`
- Delete: `d:/Projects/Trace/src/trace/stages/logical/author.py`
- Delete: `d:/Projects/Trace/src/trace/stages/logical/builder.py`
- Delete: `d:/Projects/Trace/src/trace/stages/logical/context.py`
- Delete: `d:/Projects/Trace/src/trace/stages/logical/prepare.py`
- Delete: `d:/Projects/Trace/src/trace/stages/logical/repair.py`
- Delete: `d:/Projects/Trace/src/trace/stages/logical/validator.py`
- Delete: `d:/Projects/Trace/src/trace/stages/physical/subgraph.py`
- Delete: `d:/Projects/Trace/src/trace/stages/physical/author.py`
- Delete: `d:/Projects/Trace/src/trace/stages/physical/builder.py`
- Delete: `d:/Projects/Trace/src/trace/stages/physical/context.py`
- Delete: `d:/Projects/Trace/src/trace/stages/physical/prepare.py`
- Delete: `d:/Projects/Trace/src/trace/stages/physical/repair.py`
- Delete: `d:/Projects/Trace/src/trace/stages/physical/validator.py`
- Modify: `d:/Projects/Trace/src/trace/runtime/engine.py`
- Modify: `d:/Projects/Trace/tests/integration/test_runtime_pipeline.py`

- [ ] **Step 1: Update engine and tests to import `run_*_stage` from the stage package root**
- [ ] **Step 2: Run `pytest tests/unit/stages/test_stage_package_exports.py tests/integration/test_runtime_pipeline.py -q` and confirm failures**
- [ ] **Step 3: Move logical and physical node logic into `nodes/*.py` and assemble graphs in the package `__init__.py` files**
- [ ] **Step 4: Delete the old flat stage modules and sync all imports**
- [ ] **Step 5: Run the focused stage/runtime suite and confirm it passes**

## Chunk 4: Full Verification

### Task 4: Verify the refactor across the full test suite

**Files:**
- Verify: `d:/Projects/Trace/tests`

- [ ] **Step 1: Run `pytest tests/unit/stages/test_stage_package_exports.py tests/integration/test_ground_stage.py tests/integration/test_runtime_pipeline.py -q`**
- [ ] **Step 2: Run `pytest -q`**
- [ ] **Step 3: Fix any fallout and re-run until green**
