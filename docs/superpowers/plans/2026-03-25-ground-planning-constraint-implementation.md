# Ground Planning Constraint Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the `ground` stage so it completes topology planning before freezing nodes, emits constrained natural-language constraints, and rejects vague or under-grounded outputs.

**Architecture:** Keep the persisted `ground` schema unchanged, but harden the behavior around it. Tighten the prompt contract, add deterministic guard heuristics, and adjust existing sanitize/tests so `ground` outputs are planning-complete rather than abstract intent restatements.

**Tech Stack:** Python 3.11, existing TRACE stage runtime, Pydantic v2, pytest, current `ground` prompt/schema/guard helpers.

---

## File Map

**Modify:**
- `prompts/ground.md`
- `stages/ground/constraint_refs.py`
- `stages/ground/output_schema.py`
- `stages/ground/guard.py`
- `tests/unit/test_constraint_refs.py`
- `tests/integration/test_ground_to_logical.py`
- `README.md` only if prompt/runtime behavior examples drift

## Chunk 1: Prompt Contract and Example Alignment

### Task 1: Lock the new constraint-language contract with failing tests

**Files:**
- Modify: `tests/unit/test_constraint_refs.py`
- Modify: `tests/integration/test_ground_to_logical.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_ground_guard_rejects_vague_group_phrases() -> None:
    output = GroundOutput(
        node_patterns=['PLC[1..2]'],
        logical_constraints=[],
        physical_constraints=[{'id': 'pc1', 'scope': 'topology', 'text': 'All PLC nodes must use an OpenPLC-compatible image.'}],
    )
    with pytest.raises(ValueError, match='vague node groups'):
        assert_valid(output)


def test_ground_guard_rejects_under_grounded_segment_goal() -> None:
    output = GroundOutput(
        node_patterns=['PLC[1..2]', 'SW1'],
        logical_constraints=[{'id': 'lc1', 'scope': 'topology', 'text': 'The topology must be divided into four segments.'}],
        physical_constraints=[],
    )
    with pytest.raises(ValueError, match='under-grounded'):
        assert_valid(output)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_constraint_refs.py -v`
Expected: FAIL because the current guard only checks compact reference resolution and does not reject vague groups or under-grounded goals.

- [ ] **Step 3: Add one integration-level expectation for explicit node-set wording**

```python
def test_ground_stage_contract_examples_use_explicit_node_sets() -> None:
    prompt_text = Path('prompts/ground.md').read_text(encoding='utf-8')
    assert 'All PLC nodes' not in prompt_text
    assert 'PLC[1..6]' in prompt_text
```

- [ ] **Step 4: Run the focused tests again**

Run: `pytest tests/unit/test_constraint_refs.py tests/integration/test_ground_to_logical.py -v`
Expected: FAIL only on the new guard/prompt requirements.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_constraint_refs.py tests/integration/test_ground_to_logical.py
git commit -m "test: lock ground planning constraint contract"
```

### Task 2: Rewrite the ground prompt around planning-first constraints

**Files:**
- Modify: `prompts/ground.md`

- [ ] **Step 1: Rewrite the prompt to require planning before freezing nodes**

The prompt must explicitly say:

- finish topology planning before returning output
- include all infrastructure nodes needed by the planned design
- keep the persisted schema unchanged
- refine high-level goals until they become executable

- [ ] **Step 2: Add explicit sentence families to the prompt**

Add recommended forms such as:

```text
The whole logical topology must be connected.
X must use cidr Y.
X must connect to Z through Y.
X must not directly connect to Y.
X must use image Y.
```

- [ ] **Step 3: Remove vague or contradictory examples**

Replace examples such as:

```text
All PLC nodes must use an OpenPLC-compatible image.
```

with explicit node-set wording such as:

```text
PLC[1..6] must use an OpenPLC-compatible image.
```

- [ ] **Step 4: Run the prompt-alignment tests**

Run: `pytest tests/integration/test_ground_to_logical.py -v`
Expected: PASS for the prompt-text expectation; other failures now point to guard/schema behavior.

- [ ] **Step 5: Commit**

```bash
git add prompts/ground.md tests/integration/test_ground_to_logical.py
git commit -m "docs: tighten ground planning prompt contract"
```

## Chunk 2: Deterministic Guard Heuristics

### Task 3: Extend ground constraint helpers for explicit refs and vague-phrase detection

**Files:**
- Modify: `stages/ground/constraint_refs.py`
- Modify: `tests/unit/test_constraint_refs.py`

- [ ] **Step 1: Write the failing helper tests**

```python
def test_detects_vague_group_phrase() -> None:
    assert contains_vague_node_group('All PLC nodes must use image X.') is True


def test_extracts_explicit_range_refs() -> None:
    refs = resolve_constraint_refs('PLC[1..3] must use cidr 10.10.30.0/24.', ['PLC1', 'PLC2', 'PLC3'])
    assert refs == ['PLC1', 'PLC2', 'PLC3']
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_constraint_refs.py -v`
Expected: FAIL because vague-group detection helpers do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add small deterministic helpers such as:

```python
def contains_vague_node_group(text: str) -> bool:
    ...


def contains_under_grounded_goal(text: str) -> bool:
    ...
```

Keep them pattern-based. Do not build a heavy parser.

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/unit/test_constraint_refs.py -v`
Expected: PASS for the new helper behavior.

- [ ] **Step 5: Commit**

```bash
git add stages/ground/constraint_refs.py tests/unit/test_constraint_refs.py
git commit -m "feat: add ground constraint phrase detectors"
```

### Task 4: Upgrade the ground guard from ref-checking to light structural validation

**Files:**
- Modify: `stages/ground/guard.py`
- Modify: `tests/unit/test_constraint_refs.py`

- [ ] **Step 1: Add failing tests for coverage and under-grounding**

```python
def test_ground_guard_requires_key_node_coverage() -> None:
    output = GroundOutput(
        node_patterns=['PLC1', 'SW1'],
        logical_constraints=[{'id': 'lc1', 'scope': 'node_ids', 'text': 'PLC1 must connect to SW1.'}],
        physical_constraints=[],
    )
    assert_valid(output)


def test_ground_guard_rejects_uncovered_frozen_node() -> None:
    output = GroundOutput(
        node_patterns=['PLC1', 'SW1', 'FW1'],
        logical_constraints=[{'id': 'lc1', 'scope': 'node_ids', 'text': 'PLC1 must connect to SW1.'}],
        physical_constraints=[],
    )
    with pytest.raises(ValueError, match='uncovered frozen nodes'):
        assert_valid(output)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_constraint_refs.py -v`
Expected: FAIL because the current guard does not perform coverage checks.

- [ ] **Step 3: Write minimal implementation**

Update `assert_valid()` so it now checks:

- non-empty `node_patterns`
- valid pattern expansion
- explicit node/range references resolve
- vague node-group phrases are rejected
- obviously under-grounded goals are rejected
- frozen key nodes are covered by at least one constraint

Keep the logic deterministic and conservative.

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/unit/test_constraint_refs.py -v`
Expected: PASS with the new light structural validation.

- [ ] **Step 5: Commit**

```bash
git add stages/ground/guard.py tests/unit/test_constraint_refs.py
git commit -m "feat: strengthen ground guard heuristics"
```

## Chunk 3: Schema Cleanup and Regression

### Task 5: Remove or narrow sanitize behavior that hides under-grounded planning

**Files:**
- Modify: `stages/ground/output_schema.py`
- Modify: `tests/unit/test_constraint_refs.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_sanitize_ground_output_does_not_rescue_under_grounded_segment_goal() -> None:
    output = GroundOutput.model_validate(
        {
            'node_patterns': ['PLC[1..6]', 'SW1'],
            'logical_constraints': [{'id': 'lc1', 'scope': 'node_ids', 'text': 'PLC[1..6] must be distributed across at least 2 control segments.'}],
            'physical_constraints': [],
        }
    )
    sanitized = sanitize_ground_output(output)
    assert sanitized.logical_constraints[0].text == 'PLC[1..6] must be distributed across at least 2 control segments.'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_constraint_refs.py -v`
Expected: FAIL because the current sanitize path rewrites this sentence into a weaker SW-based connection statement.

- [ ] **Step 3: Write minimal implementation**

Remove or narrow sanitize logic that silently rescues under-grounded segment-planning phrases. Let the guard reject them instead of mutating them into acceptable output.

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/unit/test_constraint_refs.py -v`
Expected: PASS; sanitize should still keep only genuinely supported cleanup such as moving topological physical constraints into logical constraints.

- [ ] **Step 5: Commit**

```bash
git add stages/ground/output_schema.py tests/unit/test_constraint_refs.py
git commit -m "refactor: stop masking weak ground planning constraints"
```

### Task 6: Run regression and align docs only where behavior changed

**Files:**
- Modify: `README.md` only if examples drift from the final prompt/guard behavior
- Modify: any touched test files if verification exposes drift

- [ ] **Step 1: Run focused ground-stage suites**

Run: `pytest tests/unit/test_constraint_refs.py tests/integration/test_ground_to_logical.py -v`
Expected: PASS.

- [ ] **Step 2: Run broader stage/runtime suites**

Run: `pytest tests/unit/test_stage_runtime.py tests/integration/test_logical_to_physical.py -v`
Expected: PASS; no regression in downstream stage wiring.

- [ ] **Step 3: Run the full test suite**

Run: `pytest -q --basetemp .pytest_run_ground_planning`
Expected: PASS; if unrelated failures exist, capture them explicitly before any final summary.

- [ ] **Step 4: Update docs only if necessary**

Make sure README examples do not contradict the final `ground` prompt contract.

- [ ] **Step 5: Commit**

```bash
git add README.md prompts/ground.md stages/ground tests/unit tests/integration
git commit -m "test: cover strengthened ground planning constraints"
```
