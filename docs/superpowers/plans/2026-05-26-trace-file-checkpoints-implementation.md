# TRACE File Checkpoints Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace JSON `func`/`args`, logical `constraint_scripts`, and physical `validator_script` flows with file-backed constraints, checkpoint Python files, controlled TGraph check APIs, and transactional mutation scripts.

**Architecture:** Implement the foundation in TGraph first: node-local ports, issue shape, view/check/editor APIs, checkpoint/mutation file runners, and initialization helpers. Then migrate Trace stages to write/read file references and use file-oriented author/repair workflows. This is a breaking migration; do not preserve old compatibility paths unless a test explicitly requires temporary scaffolding during a single task.

**Tech Stack:** Python, Pydantic, LangGraph stage nodes, pytest, subprocess sandboxing, AST validation.

---

## Reference Spec

- `docs/superpowers/specs/2026-05-26-trace-fact-checkpoint-files-design.md`

## File Structure Map

Core TGraph model and validation:

- Modify `src/tgraph/core/graph.py`: port/link endpoint semantics and id grammar validation.
- Modify `src/tgraph/operations/validate/issues.py`: remove top-level `code` dependency and make details-driven issue classification first-class.
- Modify `src/tgraph/operations/validate/view.py`: use `(node_id, port_id)` endpoint identity, expose read-only graph APIs, and add formal check APIs.
- Create `src/tgraph/operations/validate/constraint_files.py`: load and validate `logical_constraints.json` / `physical_constraints.json` with duplicate-key detection.
- Create `src/tgraph/operations/validate/checkpoint_files.py`: validate and execute `checkpoints.py` files with sandboxing.
- Create `src/tgraph/operations/mutate/editor.py`: controlled `TGraphEditor` mutation API.
- Create `src/tgraph/operations/mutate/scripts.py`: validate/execute mutation scripts transactionally.
- Create `src/tgraph/operations/init.py`: logical and physical skeleton initialization helpers.
- Modify `src/tgraph/operations/validate/policy.py`, `runner.py`, `f4_intent.py`, `__init__.py`: wire new validation context fields.
- Keep `src/tgraph/operations/patch/*` untouched or de-emphasized unless tests still use it; do not make it the new repair path.

Trace stage artifacts and nodes:

- Modify `src/trace/stages/artifacts.py`: new artifact shapes with file references.
- Modify `src/trace/storage/run_storage.py`: persist stage support files in snapshots and copy them during resume.
- Modify `src/trace/stages/ground/schemas.py`: ground artifact keeps `node_groups`, replaces embedded constraints with file references or companion file metadata.
- Modify `src/trace/stages/ground/nodes/finalize.py`: write `ground/logical_constraints.json` and `ground/physical_constraints.json`.
- Modify `src/trace/stages/logical/nodes/prepare.py`, `author.py`, `builder.py`, `validator.py`, `repair.py`, `finalize.py`: file checkpoint flow and mutation repairs.
- Modify `src/trace/stages/physical/nodes/prepare.py`, `author.py`, `builder.py`, `validator.py`, `repair.py`, `finalize.py`: physical checkpoint file flow and node-type defaults.
- Modify `src/trace/stages/logical/prompts/*.md`, `src/trace/stages/physical/prompts/*.md`, `src/trace/stages/ground/prompts/*.md`: new file and fact-kind contracts.
- Modify `src/trace/runtime/engine.py`: include support files in saved snapshots and resume.

Agent docs:

- Create `src/tgraph/agent/docs/index.md`
- Create `src/tgraph/agent/docs/tgraph_view_api.md`
- Create `src/tgraph/agent/docs/tgraph_check_api.md`
- Create `src/tgraph/agent/docs/tgraph_editor_api.md`
- Create `src/tgraph/agent/docs/fact_kinds.md`
- Create `src/tgraph/agent/docs/checkpoint_authoring.md`
- Create `src/tgraph/agent/docs/mutation_authoring.md`
- Create `src/tgraph/agent/docs/repair_playbook.md`
- Modify `README.md` and `docs/architecture/langgraph/*.md` to link rather than duplicate.

Tests:

- Add or modify tests under `tests/unit/tgraph/core/`, `tests/unit/tgraph/operations/`, `tests/unit/stages/`, and `tests/integration/`.
- Run targeted tests after each chunk; run full `pytest -q` at the end.

---

## Chunk 1: TGraph Core Endpoint And Issue Foundation

### Task 1.1: Node-local port identity

**Files:**
- Modify `src/tgraph/core/graph.py`
- Test `tests/unit/tgraph/core/test_graph.py`
- Test `tests/unit/tgraph/io/test_json.py`

- [ ] **Step 1: Write failing tests for node-local duplicate port ids**

Add tests that accept the same port id on different nodes when links include `from_node` / `to_node`:

```python
def test_ports_are_node_local_when_links_include_nodes():
    graph = TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {"id": "A", "type": "computer", "label": "A", "ports": [{"id": "_B-1"}]},
                {"id": "B", "type": "switch", "label": "B", "ports": [{"id": "_A-1"}, {"id": "_C-1"}]},
                {"id": "C", "type": "computer", "label": "C", "ports": [{"id": "_B-1"}]},
            ],
            "links": [
                {"id": "A-B-1", "from_node": "A", "from_port": "_B-1", "to_node": "B", "to_port": "_A-1"},
                {"id": "B-C-1", "from_node": "C", "from_port": "_B-1", "to_node": "B", "to_port": "_C-1"},
            ],
        }
    )
    assert graph.stage == "logical"
```

Run: `pytest tests/unit/tgraph/core/test_graph.py -q`
Expected: FAIL until endpoint validation is updated.

- [ ] **Step 2: Add id grammar tests**

Cover valid and invalid `node_id`, generated port id, and `link_key` helper validation.

Run: `pytest tests/unit/tgraph/core/test_graph.py -q`
Expected: FAIL until validators are implemented.

- [ ] **Step 3: Implement model validators**

In `src/tgraph/core/graph.py`:

- keep `Node.type` unchanged,
- validate `Node.id` against `^[A-Z][A-Z0-9_]*$`,
- validate generated/editor-facing port ids against `^_[A-Z][A-Z0-9_]*-[0-9]+$` where appropriate,
- ensure links with duplicate node-local port ids resolve by `(node_id, port_id)`,
- require `from_node` and `to_node` for new emitted graphs; temporarily allow legacy links only inside migration tests if absolutely needed.

- [ ] **Step 4: Run core/io tests**

Run: `pytest tests/unit/tgraph/core tests/unit/tgraph/io -q`
Expected: PASS after test fixtures are updated.

### Task 1.2: ValidationIssue without top-level code contract

**Files:**
- Modify `src/tgraph/operations/validate/issues.py`
- Modify callers in `src/tgraph/operations/validate/*.py`
- Test `tests/unit/tgraph/operations/test_validate.py`
- Test `tests/unit/tgraph/operations/test_validate_f4.py`

- [ ] **Step 1: Write failing test for details-driven issue shape**

Expected issue:

```python
assert issue.model_dump(mode="json") == {
    "message": "logical chain is missing direct edge A -- B",
    "severity": "error",
    "location": "links.A-B",
    "details": {
        "issue_kind": "logical.topology.chain.missing_edge",
        "fact_kind": "logical.topology.chain",
        "repair_target": "graph",
    },
}
```

Run: `pytest tests/unit/tgraph/operations/test_validate.py -q`
Expected: FAIL while `code` is still required.

- [ ] **Step 2: Update ValidationIssue schema**

Remove required `code`. Keep `message`, `severity`, `location`, `details`.

Do not add top-level `kind`.

- [ ] **Step 3: Update helper functions**

Change issue helpers in `view.py`, `checkpoints.py`, `scripts.py`, and builtins to populate `details.issue_kind`, `details.fact_kind`, and `details.repair_target`.

- [ ] **Step 4: Run validation tests**

Run: `pytest tests/unit/tgraph/operations/test_validate.py tests/unit/tgraph/operations/test_validate_f4.py -q`
Expected: PASS after fixtures are migrated.

---

## Chunk 2: Constraint Files And Formal Check APIs

### Task 2.1: Constraint file loader with duplicate-key detection

**Files:**
- Create `src/tgraph/operations/validate/constraint_files.py`
- Modify `src/tgraph/operations/validate/__init__.py`
- Test `tests/unit/tgraph/operations/test_constraint_files.py`

- [ ] **Step 1: Write loader tests**

Test:

- valid logical file loads `{"lc1": {"kind": "...", "statement": "..."}}`,
- duplicate keys produce issue with `details.issue_kind="constraint.file.duplicate_key"`,
- unknown kind produces `constraint.kind.unknown`,
- invalid JSON produces `constraint.file.invalid_json`.

Run: `pytest tests/unit/tgraph/operations/test_constraint_files.py -q`
Expected: FAIL because module does not exist.

- [ ] **Step 2: Implement loader**

Use `json.loads(..., object_pairs_hook=...)` to detect duplicate keys.

Return a model/result object such as:

```python
class ConstraintFileResult(BaseModel):
    ok: bool
    constraints: dict[str, ConstraintFact] = {}
    issues: list[ValidationIssue] = []
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/tgraph/operations/test_constraint_files.py -q`
Expected: PASS.

### Task 2.2: TGraphView endpoint indexing and read APIs

**Files:**
- Modify `src/tgraph/operations/validate/view.py`
- Test `tests/unit/tgraph/operations/test_inspect.py`
- Test `tests/unit/tgraph/operations/test_validate_f4.py`

- [ ] **Step 1: Write failing tests for node-local port lookup**

Cover:

```python
view.port("A", "_B-1")
view.links(between=["A", "B"])
view.links(between=["A", "B"], link_key="wan_primary")
view.neighbors("A")
view.paths("A", "C")
```

Run: `pytest tests/unit/tgraph/operations/test_inspect.py -q`
Expected: FAIL until view indexing is rewritten.

- [ ] **Step 2: Update TGraphView indexes**

Replace `_ports_by_id` global mapping with:

```python
_ports_by_node: dict[str, dict[str, dict]]
_links_by_id: dict[str, dict]
_link_endpoints: list[(from_node, from_port, to_node, to_port)]
```

- [ ] **Step 3: Run inspect tests**

Run: `pytest tests/unit/tgraph/operations/test_inspect.py tests/unit/tgraph/operations/test_inspect_cidrs.py -q`
Expected: PASS.

### Task 2.3: Formal logical check APIs

**Files:**
- Modify `src/tgraph/operations/validate/view.py`
- Test `tests/unit/tgraph/operations/test_check_api_logical.py`

- [ ] **Step 1: Write tests for each formal logical API**

Cover:

- `check_subnet("SW_DMZ", "10.10.10.0/24")`
- `check_interface("R_CORE", segment="SW_DMZ", ip="10.10.10.1/24")`
- `check_direct_link("WEB", "SW_DMZ", link_key=None)`
- `check_chain([...], link_keys=None)`
- `check_ring([...])`
- `check_star(center=..., leaves=[...])`
- `check_mesh([...])`

Expected failures include targeted messages and details such as `expected_edge`, `expected_cidr`, `missing_node`, `repair_target`.

Run: `pytest tests/unit/tgraph/operations/test_check_api_logical.py -q`
Expected: FAIL before APIs exist.

- [ ] **Step 2: Implement check APIs on TGraphView**

Keep methods simple and deterministic. Each method returns `list[ValidationIssue]` or issue payloads normalized by the runner.

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/tgraph/operations/test_check_api_logical.py -q`
Expected: PASS.

### Task 2.4: Formal physical check APIs

**Files:**
- Modify `src/tgraph/operations/validate/view.py`
- Test `tests/unit/tgraph/operations/test_check_api_physical.py`

- [ ] **Step 1: Write tests**

Cover:

- `check_image_exact(node, image_id)`
- `check_flavor_minimum(node, vcpu, ram, disk)`
- `check_flavor_exact(node, vcpu, ram, disk)`

For `check_image_capability`, first design should either not expose a deterministic implementation or expose a helper that accepts an explicit allowed image id/capability map supplied by caller context. Do not bake catalog knowledge into TGraph.

- [ ] **Step 2: Implement APIs**

Use node metadata only.

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/tgraph/operations/test_check_api_physical.py -q`
Expected: PASS.

---

## Chunk 3: Checkpoint File Runner

### Task 3.1: Static validation and sandbox

**Files:**
- Create `src/tgraph/operations/validate/checkpoint_files.py`
- Test `tests/unit/tgraph/operations/test_checkpoint_files.py`

- [ ] **Step 1: Write failing tests**

Cover:

- missing `check_lc1`,
- orphan `check_lc999`,
- duplicate function name,
- syntax error,
- disallowed import,
- guarded allowed import,
- invalid return shape,
- file timeout produces `details.issue_kind="checkpoint.execution.timeout"` and `scope="file"`.

Run: `pytest tests/unit/tgraph/operations/test_checkpoint_files.py -q`
Expected: FAIL.

- [ ] **Step 2: Implement AST preflight**

Implement:

- function discovery for `check_<constraint_id>`,
- import allowlist,
- duplicate function detection,
- coverage validation against loaded constraints.

- [ ] **Step 3: Implement subprocess execution**

Use one subprocess per checkpoint file. Pass graph JSON, constraints metadata, timeout seconds. Compile with checkpoint file path as filename. Use restricted builtins and guarded `__import__`.

- [ ] **Step 4: Normalize issues**

Runner auto-injects:

```python
details.setdefault("constraint_id", constraint_id)
details.setdefault("fact_kind", fact.kind)
details.setdefault("statement", fact.statement)
details.setdefault("checkpoint_function", f"check_{constraint_id}")
details.setdefault("checkpoint_path", path)
```

- [ ] **Step 5: Run checkpoint runner tests**

Run: `pytest tests/unit/tgraph/operations/test_checkpoint_files.py -q`
Expected: PASS.

### Task 3.2: Wire checkpoint file runner into validate_graph

**Files:**
- Modify `src/tgraph/operations/validate/policy.py`
- Modify `src/tgraph/operations/validate/f4_intent.py`
- Modify `src/tgraph/operations/validate/runner.py`
- Modify `src/tgraph/operations/validate/__init__.py`
- Test `tests/unit/tgraph/operations/test_validate_f4.py`

- [ ] **Step 1: Write failing integration-ish unit test**

Construct a temp constraints file and checkpoint file. Validate a graph that is missing a chain edge. Assert validate report contains a graph repair issue.

- [ ] **Step 2: Add ValidationContext fields**

Add:

```python
constraint_files: dict[str, Path | str]
checkpoint_files: dict[str, Path | str]
checkpoint_timeout_seconds: int = 5
checkpoint_max_processes: int = 4
```

- [ ] **Step 3: Invoke file runner in F4**

Do not run old `constraint_scripts`, `checkpoints`, or `validator_script` in the new path.

- [ ] **Step 4: Run F4 tests**

Run: `pytest tests/unit/tgraph/operations/test_validate_f4.py -q`
Expected: PASS.

---

## Chunk 4: TGraphEditor And Mutation Scripts

### Task 4.1: Controlled editor API

**Files:**
- Create `src/tgraph/operations/mutate/editor.py`
- Create `src/tgraph/operations/mutate/__init__.py`
- Test `tests/unit/tgraph/operations/test_editor.py`

- [ ] **Step 1: Write editor tests**

Cover:

- `ensure_direct_link` creates stable link/port ids,
- repeated `ensure_direct_link` is idempotent,
- explicit `link_key` creates semantic parallel links,
- `ensure_chain`, `ensure_ring`, `ensure_star`, `ensure_mesh`,
- `ensure_subnet` sets all switch ports to CIDR,
- `ensure_interface` links node to segment and sets both port CIDRs,
- `remove_direct_link` removes exactly one link and endpoint ports,
- `remove_links_between` reports destructive affected ids,
- `remove_node` cascade behavior.

Run: `pytest tests/unit/tgraph/operations/test_editor.py -q`
Expected: FAIL.

- [ ] **Step 2: Implement editor**

Editor wraps a mutable copy of `TGraph`. It should not expose raw `nodes` / `links` mutation.

- [ ] **Step 3: Run editor tests**

Run: `pytest tests/unit/tgraph/operations/test_editor.py -q`
Expected: PASS.

### Task 4.2: Mutation script runner

**Files:**
- Create `src/tgraph/operations/mutate/scripts.py`
- Test `tests/unit/tgraph/operations/test_mutation_scripts.py`

- [ ] **Step 1: Write failing tests**

Cover:

- successful `mutate(tgraph)` commits changed graph,
- mutation runtime exception leaves original graph unchanged,
- disallowed import fails,
- timeout fails,
- validation after mutation failure leaves original graph unchanged.

- [ ] **Step 2: Implement transactional runner**

Run script in sandbox against graph copy. Return:

```python
class MutationExecutionResult(BaseModel):
    ok: bool
    graph: TGraph | None
    issues: list[ValidationIssue]
    operations: list[dict] = []
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/tgraph/operations/test_mutation_scripts.py -q`
Expected: PASS.

---

## Chunk 5: Initialization Helpers

### Task 5.1: Logical skeleton init

**Files:**
- Create `src/tgraph/operations/init.py`
- Modify `src/tgraph/__init__.py`
- Modify `src/trace/stages/logical/graph_seed.py`
- Test `tests/unit/tgraph/operations/test_init.py`
- Test `tests/unit/stages/logical/test_logical_prepare_node.py`

- [ ] **Step 1: Write tests**

Assert `init_logical_skeleton(node_groups)` expands compact ranges, creates nodes only, and does not infer links/ports.

- [ ] **Step 2: Implement helper**

Move or reuse logic from `trace.stages.logical.graph_seed`.

- [ ] **Step 3: Wire logical prepare**

Logical prepare should call TGraph helper.

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/tgraph/operations/test_init.py tests/unit/stages/logical/test_logical_prepare_node.py -q`
Expected: PASS.

### Task 5.2: Physical skeleton init with node-type defaults

**Files:**
- Modify `src/tgraph/operations/init.py`
- Modify `src/trace/stages/physical/graph_seed.py`
- Modify `src/trace/stages/physical/nodes/prepare.py`
- Test `tests/unit/tgraph/operations/test_init.py`
- Test `tests/unit/stages/physical/test_physical_prepare_node.py`

- [ ] **Step 1: Write tests**

Assert physical skeleton:

- copies logical topology,
- sets stage to physical,
- applies node-type defaults,
- allows `switch` defaults to be null,
- does not overwrite existing non-empty image/flavor.

- [ ] **Step 2: Implement helper and default policy plumbing**

Keep default catalog/policy in Trace, not TGraph.

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/tgraph/operations/test_init.py tests/unit/stages/physical/test_physical_prepare_node.py -q`
Expected: PASS.

---

## Chunk 6: Trace File Artifact Migration

> **Status:** Task 6.1 completed in prior work; Task 6.2 completed in 2026-05-27 alignment pass.

### Task 6.1: Artifact schemas and storage support files

**Files:**
- Modify `src/trace/stages/artifacts.py`
- Modify `src/trace/storage/run_storage.py`
- Modify `src/trace/runtime/engine.py`
- Test `tests/unit/stages/test_artifacts.py`
- Test `tests/unit/storage/test_run_storage.py` if present; otherwise create it.
- Test `tests/unit/runtime/test_resume.py` or existing runtime resume tests.

- [ ] **Step 1: Write failing tests**

Test artifacts include file references:

```json
{
  "graph": {...},
  "constraint_files": {"logical": "ground/logical_constraints.json"},
  "checkpoint_files": {"logical": "logical/checkpoints.py"}
}
```

Test storage saves/copies support files during resume.

- [ ] **Step 2: Implement schemas**

Remove `constraint_scripts`, `checkpoints`, `validator_script` from final stage artifact contracts.

- [ ] **Step 3: Implement storage helpers**

Add methods to write/read support text/json files under run stage dirs. Resume copies them with artifact snapshots.

- [ ] **Step 4: Run tests**

Run targeted storage/artifact/runtime tests.

### Task 6.2: Ground writes constraint files

**Files:**
- Modify `src/trace/stages/ground/schemas.py`
- Modify `src/trace/stages/ground/nodes/finalize.py`
- Modify `src/trace/stages/ground/prompts/author.md`
- Modify `src/trace/stages/ground/prompts/evaluator.md`
- Test `tests/unit/stages/test_ground_schemas.py`
- Test `tests/unit/stages/test_ground_author_node.py`

- [x] **Step 1: Write schema tests**

Ground artifact keeps `node_groups` and emits references for `ground/logical_constraints.json`, `ground/physical_constraints.json`.

- [x] **Step 2: Update prompts**

Ground author should output facts keyed by id and kind/statement. If role client cannot write files directly yet, stage finalize translates structured output into files.

- [x] **Step 3: Implement finalize file writing**

Use duplicate-key-safe writer path. Ensure ids are not repeated.

- [x] **Step 4: Run ground tests**

Run: `pytest tests/unit/stages/test_ground_* -q`
Expected: PASS.

---

## Chunk 7: Logical Stage Migration

> **Status:** Completed (file-backed constraints from `ground/`, checkpoint authoring, mutation repair).

### Task 7.1: Logical author writes checkpoints.py

**Files:**
- Modify `src/trace/stages/logical/nodes/author.py`
- Modify `src/trace/stages/logical/prompts/author.md`
- Test `tests/unit/stages/logical/test_author_node.py`

- [x] **Step 1: Write failing test**

Stub agent writes `logical/checkpoints.py` through file tool or returned file content. Assert `author_output` contains file reference only.

- [x] **Step 2: Replace constraint_script tools**

Remove `put_constraint_script` flow. Provide scoped file tools or a simple batch file writer for `logical/checkpoints.py`.

- [x] **Step 3: Validate generated checkpoint file**

Run checkpoint file validation immediately after authoring.

- [x] **Step 4: Run test**

Run: `pytest tests/unit/stages/logical/test_author_node.py -q`
Expected: PASS.

### Task 7.2: Logical builder/validator/finalize consume file refs

**Files:**
- Modify `src/trace/stages/logical/nodes/builder.py`
- Modify `src/trace/stages/logical/nodes/validator.py`
- Modify `src/trace/stages/logical/nodes/finalize.py`
- Modify `src/trace/stages/logical/prompts/builder.md`
- Test `tests/unit/stages/logical/test_builder_node.py`
- Test `tests/unit/stages/logical/test_logical_validator_node.py`

- [x] **Step 1: Write validator test**

Use temp `ground/logical_constraints.json` and `logical/checkpoints.py`. Missing chain edge should route to repair with `repair_target="graph"`.

- [x] **Step 2: Implement file validation context**

Logical validator passes constraint/checkpoint file refs into `validate_graph`.

- [x] **Step 3: Update builder**

Builder only produces graph. It does not output constraints/checkpoints.

- [x] **Step 4: Run tests**

Run: `pytest tests/unit/stages/logical/test_builder_node.py tests/unit/stages/logical/test_logical_validator_node.py -q`
Expected: PASS.

### Task 7.3: Logical repair writes mutation attempts

**Files:**
- Modify `src/trace/stages/logical/nodes/repair.py`
- Modify `src/trace/stages/logical/prompts/repair.md`
- Test `tests/unit/stages/logical/test_repair_node.py`

- [x] **Step 1: Write failing repair test**

Given a missing chain edge issue, repair agent writes `logical/mutations/attempt_2.py` with `ensure_direct_link`. Runtime executes mutation and updates draft graph only if validation passes.

- [x] **Step 2: Replace graph patch tooling**

Remove preferred `apply_graph_patch` flow for logical repair. Use file tools + mutation execution tool.

- [x] **Step 3: Run logical repair tests**

Run: `pytest tests/unit/stages/logical/test_repair_node.py -q`
Expected: PASS.

---

## Chunk 8: Physical Stage Migration

> **Status:** Completed (physical checkpoints, scoped constraint files, mutation repair).

### Task 8.1: Physical prepare with defaults

**Files:**
- Modify `src/trace/stages/physical/nodes/prepare.py`
- Modify `src/trace/tools/images/catalog.py` only if default lookup is reused simply
- Test `tests/unit/stages/physical/test_physical_prepare_node.py`

- [x] **Step 1: Write tests for node-type defaults**

Switch can remain `image=None`, `flavor=None`. Computer/router defaults are applied from policy.

- [x] **Step 2: Implement prepare**

Use `init_physical_skeleton`.

- [x] **Step 3: Run test**

Run: `pytest tests/unit/stages/physical/test_physical_prepare_node.py -q`
Expected: PASS.

### Task 8.2: Physical author/checkpoints/validator

**Files:**
- Modify `src/trace/stages/physical/nodes/author.py`
- Modify `src/trace/stages/physical/nodes/builder.py`
- Modify `src/trace/stages/physical/nodes/validator.py`
- Modify `src/trace/stages/physical/prompts/author.md`
- Modify `src/trace/stages/physical/prompts/builder.md`
- Test `tests/unit/stages/physical/test_physical_author_node.py`
- Test `tests/unit/stages/physical/test_physical_builder_node.py`
- Test `tests/unit/stages/physical/test_physical_validator_node.py`

- [x] **Step 1: Write tests**

Physical author writes `physical/checkpoints.py`. Validator runs against `ground/physical_constraints.json` and checkpoint file.

- [x] **Step 2: Implement author file flow**

Agent reads static image/flavor docs if needed. First design trusts its checkpoint logic for capability facts.

- [x] **Step 3: Update validator**

Remove required all-node `image/flavor` validation. Required metadata comes from default policy and physical checkpoint failures.

- [x] **Step 4: Run tests**

Run: `pytest tests/unit/stages/physical/test_physical_* -q`
Expected: PASS.

### Task 8.3: Physical repair with mutation scripts

**Files:**
- Modify `src/trace/stages/physical/nodes/repair.py`
- Modify `src/trace/stages/physical/prompts/repair.md`
- Test `tests/unit/stages/physical/test_physical_repair_node.py`

- [x] **Step 1: Write failing test**

Given a physical image/flavor issue, repair writes `physical/mutations/attempt_N.py` and sets metadata with editor API.

- [x] **Step 2: Implement mutation execution**

Use mutation runner and commit only after validation.

- [x] **Step 3: Run tests**

Run: `pytest tests/unit/stages/physical/test_physical_repair_node.py -q`
Expected: PASS.

---

## Chunk 9: Agent Docs And Top-Level Docs

### Task 9.1: Create agent docs

**Files:**
- Create `src/tgraph/agent/docs/index.md`
- Create `src/tgraph/agent/docs/tgraph_view_api.md`
- Create `src/tgraph/agent/docs/tgraph_check_api.md`
- Create `src/tgraph/agent/docs/tgraph_editor_api.md`
- Create `src/tgraph/agent/docs/fact_kinds.md`
- Create `src/tgraph/agent/docs/checkpoint_authoring.md`
- Create `src/tgraph/agent/docs/mutation_authoring.md`
- Create `src/tgraph/agent/docs/repair_playbook.md`
- Test `tests/unit/tgraph/agent/test_agent_docs.py`

- [x] **Step 1: Write docs presence test**

Assert docs exist and contain key strings such as `check_chain`, `ensure_direct_link`, `logical.topology.chain`, `repair_target`.

- [x] **Step 2: Write concise docs**

Each doc should be short, example-heavy, and searchable.

- [x] **Step 3: Run docs test**

Run: `pytest tests/unit/tgraph/agent/test_agent_docs.py -q`
Expected: PASS.

### Task 9.2: Update README and architecture docs

**Files:**
- Modify `README.md`
- Modify `docs/architecture/langgraph/README.zh.md`
- Modify `docs/architecture/langgraph/ground/README.zh.md`
- Modify `docs/architecture/langgraph/logical/README.zh.md`
- Modify `docs/architecture/langgraph/physical/README.zh.md`
- Test `tests/unit/config/test_prompts.py` if prompt references are asserted

- [ ] **Step 1: Update docs**

Link to `src/tgraph/agent/docs/index.md` and describe file-backed constraints/checkpoints at a high level only.

- [ ] **Step 2: Run doc/prompt tests**

Run: `pytest tests/unit/config/test_prompts.py tests/unit/tgraph/agent/test_agent_docs.py -q`
Expected: PASS.

---

## Chunk 10: End-To-End Migration And Cleanup

### Task 10.1: Integration pipeline update

**Files:**
- Modify `tests/integration/test_runtime_pipeline.py`
- Modify any fixtures under `tests/demo/`
- Modify `README.md` examples if needed

- [x] **Step 1: Update integration expectations**

Expected run snapshot contains:

```text
ground/logical_constraints.json
ground/physical_constraints.json
logical/checkpoints.py
physical/checkpoints.py
logical/mutations/attempt_*.py when repair happens
physical/mutations/attempt_*.py when repair happens
```

- [x] **Step 2: Remove old artifact assumptions**

No final artifact should contain logical `constraint_scripts` or physical `checkpoints` / `validator_script`.

- [x] **Step 3: Run integration tests**

Run: `pytest tests/integration/test_runtime_pipeline.py -q`
Expected: PASS.

### Task 10.2: Remove obsolete code and tests

**Files:**
- Modify `src/trace/stages/repair_tools.py`
- Modify or delete tests that only assert legacy checkpoint/constraint_script behavior.
- Search all code/docs.

- [ ] **Step 1: Search for obsolete terms**

Run:

```powershell
rg -n "constraint_scripts|validator_script|CheckpointSpec|checkpoints\\]|func\\\"|args\\\"" src tests docs -S
```

Expected: only intentional historical spec references or no active references.

- [ ] **Step 2: Remove active legacy paths**

Delete or rewrite active code paths. Historical docs in `docs/superpowers/specs/` may remain.

- [x] **Step 3: Run full tests**

Run: `pytest -q`
Expected: all tests pass.

### Task 10.3: Final verification

**Files:**
- No code changes unless verification reveals issues.

- [ ] **Step 1: Run targeted grep**

Run:

```powershell
rg -n "constraint_scripts|validator_script|func|args" src/trace src/tgraph tests/unit -S
```

Expected: no active legacy logical/physical artifact contract references, except Python function arguments that are unrelated and obvious.

- [x] **Step 2: Run full suite**

Run: `pytest -q`
Expected: PASS.

- [x] **Step 3: Summarize migration**

Prepare a concise summary listing:

- new file layout,
- new validation/mutation APIs,
- removed legacy fields,
- tests run.

---

## Migration Notes (2026-05-27)

**Ground / evaluator**

- Removed `GroundOptimizerBrief`; `GroundEvaluationReport` is `{passed, issues, notes}` with `GroundIssue.details.issue_kind` required.
- `evaluator_node` runs `load_constraint_text` for structural issues before LLM semantic judging.
- `finalize` writes `ground/logical_constraints.json` and `ground/physical_constraints.json` (physical file only when non-empty).

**Cross-stage constraint scope**

- `logical.prepare` and `physical.prepare` each inherit only their stage’s constraint file reference from `ground_artifact.constraint_files`. Passing both scopes into a single stage caused F4 validation to require checkpoints for the other stage and broke repair loops.

**Runtime / CLI**

- `RunState.support_files` merges across stages; logical/physical receive `inherited_support_files` from the engine.
- `main.py` prints `error_stage` / `error_type` / `error_message` and exits non-zero when `status != completed`.

**Physical validator policy**

- `repair_tools._validation_context` uses `required_node_fields=[]` for physical; missing image/flavor is reported via checkpoint files, not blanket node field requirements.

**Sandbox / tests**

- Expanded `SAFE_BUILTINS` / `ALLOWED_MODULES` per spec (including `itertools`).
- `tests/conftest.py` sets `TGRAPH_EXECUTION_MODE=inline` so Windows pytest does not spawn hung sandbox workers; inline execution uses `threading` joins for timeout tests.
- Production still defaults to multiprocessing `spawn` when `TGRAPH_EXECUTION_MODE` is unset.

**Agent docs**

- Added `src/tgraph/agent/docs/*` (8 files); `prompt_contracts.py` appends `agent/docs/index.md` to stage contracts.

**Outstanding / deferred**

- Task 9.2 (README + `docs/architecture/langgraph/*` links) not updated in this pass.
- Live `trace run tests/demo/demo.md --run-id demo-006` failed at logical repair with `unknown inspect view: node_id` (LLM tool misuse); integration mocks pass (`pytest -q`: 175 passed).
