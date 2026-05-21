# Contract Tightening Cleanup Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove active compatibility shims that keep TRACE's runtime contract wider than its documented contract, starting with schema-level coercions and ending with tool-surface cleanup.

**Architecture:** Tighten the contract from the outside in. First remove schema and parser normalizers that silently accept legacy shapes, then simplify validator-view aliases so custom checks see one stable shape, then decide whether the bound tool wrapper needs a stage-neutral refactor after the strict-contract changes land. Every behavior change starts with a failing test and is verified with focused unit coverage before broader pipeline validation.

**Tech Stack:** Python, Pydantic v2, LangGraph/LangChain structured tools, pytest

---

## Chunk 1: Strict-Contract Foundations

### Task 1: Remove permissive ground-schema coercions

**Files:**
- Modify: `src/trace/stages/ground/schemas.py`
- Test: `tests/unit/stages/test_ground_schemas.py`

- [ ] **Step 1: Write failing tests for rejected legacy ground shapes**

Add tests covering at least:
- string `optimizer_brief`
- string node-group entries
- string constraint entries
- legacy semantic node-type aliases like `gateway` / `firewall`

- [ ] **Step 2: Run the targeted ground schema tests to verify they fail**

Run: `pytest -q tests/unit/stages/test_ground_schemas.py`
Expected: FAIL because the schema still coerces legacy input instead of rejecting it.

- [ ] **Step 3: Remove the ground-schema compatibility normalizers**

Update `GroundArtifact`, `GroundIssue`, and `GroundOptimizerBrief` so they validate the documented shapes directly instead of rewriting broad legacy input into canonical objects.

- [ ] **Step 4: Run the targeted ground schema tests to verify they pass**

Run: `pytest -q tests/unit/stages/test_ground_schemas.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/trace/stages/ground/schemas.py tests/unit/stages/test_ground_schemas.py
git commit -m "refactor: tighten ground schema contract"
```

### Task 2: Remove checkpoint auto-normalization from the shared stage schema

**Files:**
- Modify: `src/trace/stages/common.py`
- Modify: `src/trace/stages/logical/prompts/author.md`
- Modify: `src/trace/stages/physical/prompts/author.md`
- Test: `tests/unit/stages/logical/test_author_node.py`
- Test: `tests/unit/stages/physical/test_physical_validator_node.py`
- Test: `tests/integration/test_runtime_pipeline.py`

- [ ] **Step 1: Write failing tests for missing `description` and positional/non-dict `args`**

Add focused tests asserting `CheckpointSpec` rejects:
- missing `description`
- list/tuple `args`
- `args=None` when a dict is required

- [ ] **Step 2: Run the focused checkpoint-schema tests to verify they fail**

Run: `pytest -q tests/unit/stages/logical/test_author_node.py tests/unit/stages/physical/test_physical_validator_node.py tests/integration/test_runtime_pipeline.py`
Expected: FAIL once the new strict tests are present, because runtime normalization still accepts the legacy checkpoint shape.

- [ ] **Step 3: Remove `CheckpointSpec` compatibility rewriting and align prompts**

Delete the auto-fill / positional-arg normalization path in `src/trace/stages/common.py`, then ensure the author prompts explicitly require full checkpoint objects with `description` and dict `args`.

- [ ] **Step 4: Run the focused checkpoint tests to verify they pass**

Run: `pytest -q tests/unit/stages/logical/test_author_node.py tests/unit/stages/physical/test_physical_validator_node.py tests/integration/test_runtime_pipeline.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/trace/stages/common.py src/trace/stages/logical/prompts/author.md src/trace/stages/physical/prompts/author.md tests/unit/stages/logical/test_author_node.py tests/unit/stages/physical/test_physical_validator_node.py tests/integration/test_runtime_pipeline.py
git commit -m "refactor: require explicit checkpoint schema"
```

### Task 3: Remove the top-level `edges -> links` graph alias

**Files:**
- Modify: `src/trace/tools/tgraph/model.py`
- Modify: `src/trace/tools/tgraph/contract.md`
- Test: `tests/unit/tools/tgraph/test_model.py`

- [ ] **Step 1: Write a failing test that rejects `edges`**

Add a test asserting `TGraphJSON.model_validate(...)` raises when a payload uses `edges` instead of `links`.

- [ ] **Step 2: Run the model tests to verify they fail**

Run: `pytest -q tests/unit/tools/tgraph/test_model.py`
Expected: FAIL because the parser still rewrites `edges` into `links`.

- [ ] **Step 3: Remove the alias and keep contract docs aligned**

Delete `_coerce_edges_to_links` and update the contract text so `links` is the only accepted top-level relationship key.

- [ ] **Step 4: Run the model tests to verify they pass**

Run: `pytest -q tests/unit/tools/tgraph/test_model.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/trace/tools/tgraph/model.py src/trace/tools/tgraph/contract.md tests/unit/tools/tgraph/test_model.py
git commit -m "refactor: require canonical tgraph links key"
```

## Chunk 2: Validator-View Surface Cleanup

### Task 4: Remove compatibility link aliases from the intent SDK view

**Files:**
- Modify: `src/trace/tools/tgraph/validate/intent_sdk.py`
- Modify: `src/trace/tools/tgraph/contract.md`
- Test: `tests/unit/tools/tgraph/test_graph_core.py`

- [ ] **Step 1: Write failing tests for canonical-only link exposure**

Replace the alias-based test coverage with canonical expectations:
- `get_link(...)` exposes `id`, `from_port`, `to_port`, `from_node`, `to_node`
- `list_links(node_id=...)` exposes canonical link fields plus `peer_node` / `peer_port`
- no `source`, `target`, `ends`, or `ports` aliases

- [ ] **Step 2: Run the graph-core tests to verify they fail**

Run: `pytest -q tests/unit/tools/tgraph/test_graph_core.py`
Expected: FAIL because `IntentTGraphView` still emits compatibility aliases.

- [ ] **Step 3: Remove alias emission and align the contract**

Delete validator-view alias generation and keep only the canonical link fields plus the documented relative helper fields.

- [ ] **Step 4: Run the graph-core tests to verify they pass**

Run: `pytest -q tests/unit/tools/tgraph/test_graph_core.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/trace/tools/tgraph/validate/intent_sdk.py src/trace/tools/tgraph/contract.md tests/unit/tools/tgraph/test_graph_core.py
git commit -m "refactor: expose canonical link fields in intent sdk"
```

## Chunk 3: Tool-Surface Refactor Decision

### Task 5: Decide and implement the smallest safe bound-tool cleanup

**Files:**
- Modify: `src/trace/tools/tgraph/protocol.py`
- Modify: `src/trace/stages/logical/nodes/repair.py`
- Modify: `src/trace/stages/physical/nodes/repair.py`
- Test: `tests/unit/tools/tgraph/test_graph_core.py`
- Test: `tests/unit/stages/logical/test_repair_node.py`
- Test: `tests/unit/stages/physical/test_physical_repair_node.py`

- [ ] **Step 1: Write a failing test that captures the desired post-cleanup tool contract**

Choose one of these explicitly and encode it in tests:
- keep the wrapper logical-only and rename/re-scope it honestly
- or make the wrapper stage-neutral with explicit artifact-key parameters

- [ ] **Step 2: Run the focused repair/tool tests to verify they fail**

Run: `pytest -q tests/unit/tools/tgraph/test_graph_core.py tests/unit/stages/logical/test_repair_node.py tests/unit/stages/physical/test_physical_repair_node.py`
Expected: FAIL because the current wrapper still hardcodes logical artifact names.

- [ ] **Step 3: Implement the smallest safe refactor**

Apply the chosen direction without adding compatibility wrappers. If stage-neutrality is too coupled after the earlier cleanups, rename and narrow the logical-only abstraction instead of inventing an ambiguous shared interface.

- [ ] **Step 4: Run the focused repair/tool tests to verify they pass**

Run: `pytest -q tests/unit/tools/tgraph/test_graph_core.py tests/unit/stages/logical/test_repair_node.py tests/unit/stages/physical/test_physical_repair_node.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/trace/tools/tgraph/protocol.py src/trace/stages/logical/nodes/repair.py src/trace/stages/physical/nodes/repair.py tests/unit/tools/tgraph/test_graph_core.py tests/unit/stages/logical/test_repair_node.py tests/unit/stages/physical/test_physical_repair_node.py
git commit -m "refactor: clarify tgraph repair tool surface"
```

## Chunk 4: Final Verification

### Task 6: Run focused and end-to-end verification

**Files:**
- Modify: `docs/architecture/langgraph/README.zh.md`
- Modify: `docs/architecture/langgraph/logical/README.zh.md`
- Modify: `docs/architecture/langgraph/physical/README.zh.md`
- Modify: `docs/architecture/langgraph/ground/README.zh.md`

- [ ] **Step 1: Update architecture docs if runtime behavior changed**

Document only behavior that actually changed during the cleanup.

- [ ] **Step 2: Run the focused test suites**

Run:
`pytest -q tests/unit/stages/test_ground_schemas.py tests/unit/tools/tgraph/test_model.py tests/unit/tools/tgraph/test_graph_core.py tests/unit/stages/logical/test_author_node.py tests/unit/stages/logical/test_repair_node.py tests/unit/stages/physical/test_physical_validator_node.py tests/unit/stages/physical/test_physical_repair_node.py tests/integration/test_runtime_pipeline.py`

Expected: PASS

- [ ] **Step 3: Run the demo pipeline**

Run: `trace run tests/demo/demo.md`
Expected: `status:completed`

- [ ] **Step 4: Commit docs and verification-driven follow-ups**

```bash
git add docs/architecture/langgraph/README.zh.md docs/architecture/langgraph/logical/README.zh.md docs/architecture/langgraph/physical/README.zh.md docs/architecture/langgraph/ground/README.zh.md
git commit -m "docs: align architecture with tightened contracts"
```
