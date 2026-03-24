# Real Three-Stage Agent Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the default fake fixture pipeline with a real patch-first `ground -> logical -> physical` runtime that preserves graph artifacts, supports natural-language constraints with compact node references, and can switch to the real LangChain backend from config.

**Architecture:** Keep `ground` artifact-first and natural-language-first, but move `logical` and `physical` to round outputs (`checkpoints/script + patch_ops`) that runtime turns into authoritative graph artifacts. Use split sub-rounds (`check_author`, `graph_builder`, `repair`) so validation logic is authored before graph construction, and keep physical from mutating passed logical connectivity.

**Tech Stack:** Python 3.11, Pydantic v2, LangChain/OpenAI adapter, existing TRACE artifact store, pytest, orjson, current `tools/tgraph` graph/patch helpers.

---

**Execution note:** User explicitly asked to execute in the current workspace after writing this plan. Do not create a worktree for this run.

## File Map

**Create:**
- `app/round_outputs.py` — round-output models for `logical` and `physical`
- `app/stage_graphs.py` — logical/physical skeleton builders and final-artifact assembly helpers
- `stages/ground/constraint_refs.py` — compact node-reference extraction and resolution from natural-language constraints
- `tests/unit/test_constraint_refs.py` — parser and ground self-check tests
- `tests/unit/test_stage_graphs.py` — skeleton and graph-assembly tests
- `tests/integration/test_patch_first_logical.py` — logical split-round integration path
- `tests/integration/test_patch_first_physical.py` — physical split-round integration path

**Modify:**
- `agent/types.py` — request metadata for stage mode/round context if needed
- `app/contracts.py` — stage mode metadata and failure classification contracts
- `app/container.py` — select fake vs LangChain backend from config and stop hard-wiring default fixtures
- `app/stage_runtime.py` — orchestrate `check_author`, `graph_builder`, and `repair`; persist final artifacts from round outputs
- `app/checkpoint_runner.py` — allow logical+physical checkpoint combination for physical validation
- `artifacts/summarizer.py` — richer repair context with latest patch summary and affected scopes
- `stages/ground/output_schema.py` — simplify constraint items so original text stays authoritative
- `stages/ground/guard.py` — ground self-check for compact node references
- `stages/logical/output_schema.py` — shift from final-graph output to round-output contract
- `stages/logical/guard.py` — validate authored checkpoints/script instead of direct final graph requirement
- `stages/logical/spec.py` — stage metadata for split-round runtime path
- `stages/physical/output_schema.py` — shift from final-graph output to round-output contract
- `stages/physical/guard.py` — validate authored checkpoints/script instead of direct final graph requirement
- `stages/physical/spec.py` — stage metadata for split-round runtime path
- `validators/patching.py` — apply richer patch plans through a stable runtime helper
- `tools/tgraph/ops/patch.py` — add the first range/batch-aware patch ops required by runtime
- `tests/unit/test_stage_runtime.py` — runtime orchestration expectations
- `tests/unit/test_tplan_runner.py` — final artifact expectations after stage execution
- `tests/unit/test_agent_facade.py` — backend-selection coverage if request shape changes
- `tests/integration/test_ground_to_logical.py` — remove final-graph fixture assumption
- `tests/integration/test_logical_to_physical.py` — remove final-graph fixture assumption and assert combined validation inputs
- `README.md` — document real patch-first flow and config-driven backend selection
- `prompts/ground.md` — real grounding instructions with natural-language constraint style and compact refs
- `prompts/logical.md` — split `check_author`/`graph_builder`/`repair` guidance
- `prompts/physical.md` — split `check_author`/`graph_builder`/`repair` guidance and physical-boundary rule

## Chunk 1: Contracts and Grounding Primitives

### Task 1: Define round-output contracts and stage failure types

**Files:**
- Create: `app/round_outputs.py`
- Modify: `app/contracts.py`
- Modify: `stages/logical/output_schema.py`
- Modify: `stages/physical/output_schema.py`
- Test: `tests/unit/test_stage_runtime.py`

- [ ] **Step 1: Write the failing test**

```python
def test_logical_round_output_accepts_checkpoints_and_patch_ops_only() -> None:
    payload = {
        'logical_checkpoints': [{'id': 'cp1', 'function_name': 'f1_format', 'description': 'format', 'input_params': {}}],
        'logical_patch_ops': [{'op': 'add_node', 'value': {'id': 'PLC1', 'type': 'computer', 'label': 'PLC1', 'ports': [], 'image': None, 'flavor': None}}],
        'logical_validator_script': None,
    }
    model = LogicalRoundOutput.model_validate(payload)
    assert model.logical_patch_ops[0]['op'] == 'add_node'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_stage_runtime.py::test_logical_round_output_accepts_checkpoints_and_patch_ops_only -v`
Expected: FAIL because `LogicalRoundOutput` does not exist and current logical schema still requires `tgraph_logical`.

- [ ] **Step 3: Write minimal implementation**

```python
class LogicalRoundOutput(BaseModel):
    logical_checkpoints: list[CheckpointSpec] = Field(default_factory=list)
    logical_patch_ops: list[dict[str, Any]] = Field(default_factory=list)
    logical_validator_script: str | None = None
```

Also add matching `PhysicalRoundOutput` and explicit failure-type enums or string constants in `app/contracts.py`.

- [ ] **Step 4: Run targeted tests to verify they pass**

Run: `pytest tests/unit/test_stage_runtime.py -v`
Expected: PASS for the new contract coverage; existing failures now point only to runtime orchestration gaps.

- [ ] **Step 5: Commit**

```bash
git add app/round_outputs.py app/contracts.py stages/logical/output_schema.py stages/physical/output_schema.py tests/unit/test_stage_runtime.py
git commit -m "feat: add round output contracts"
```

### Task 2: Add compact node-reference parsing and ground self-checks

**Files:**
- Create: `stages/ground/constraint_refs.py`
- Create: `tests/unit/test_constraint_refs.py`
- Modify: `stages/ground/output_schema.py`
- Modify: `stages/ground/guard.py`
- Modify: `app/stage_runtime.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_resolve_compact_node_refs_from_constraint_text() -> None:
    refs = resolve_constraint_refs(
        text='PLC[1..3] 必须位于两个子网中',
        available_ids=['PLC1', 'PLC2', 'PLC3', 'HMI1'],
    )
    assert refs == ['PLC1', 'PLC2', 'PLC3']


def test_ground_guard_rejects_unknown_compact_refs() -> None:
    output = GroundOutput(
        node_patterns=['PLC[1..2]'],
        logical_constraints=[{'id': 'lc1', 'scope': 'node_ids', 'text': 'PLC[1..3] 必须隔离'}],
        physical_constraints=[],
    )
    with pytest.raises(ValueError):
        assert_valid(output)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_constraint_refs.py -v`
Expected: FAIL because parser helpers do not exist and current `ConstraintItem` still expects `targets`.

- [ ] **Step 3: Write minimal implementation**

```python
COMPACT_REF_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_-]*)\[(\d+)\.\.(\d+)\]")

def resolve_constraint_refs(text: str, available_ids: list[str]) -> list[str]:
    ...
```

Remove `targets` from the ground constraint schema, update the guard to resolve compact refs against `expand_node_patterns(node_patterns)`, and call the guard from runtime before persisting `ground` outputs.

- [ ] **Step 4: Run targeted tests to verify they pass**

Run: `pytest tests/unit/test_constraint_refs.py tests/unit/test_stage_runtime.py -v`
Expected: PASS for parser and ground validation behavior.

- [ ] **Step 5: Commit**

```bash
git add stages/ground/constraint_refs.py stages/ground/output_schema.py stages/ground/guard.py app/stage_runtime.py tests/unit/test_constraint_refs.py tests/unit/test_stage_runtime.py
git commit -m "feat: validate compact refs in ground constraints"
```

## Chunk 2: Logical Patch-First Runtime

### Task 3: Add skeleton builders and runtime-owned graph assembly helpers

**Files:**
- Create: `app/stage_graphs.py`
- Create: `tests/unit/test_stage_graphs.py`
- Modify: `validators/patching.py`
- Modify: `tools/tgraph/ops/patch.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_build_logical_skeleton_includes_all_frozen_nodes() -> None:
    graph = build_logical_skeleton(['PLC1', 'PLC2'])
    assert [node['id'] for node in graph['nodes']] == ['PLC1', 'PLC2']
    assert graph['links'] == []


def test_apply_patch_ops_supports_expand_nodes_from_pattern() -> None:
    graph = {'profile': 'logical.v1', 'nodes': [], 'links': []}
    patched = apply_patch_ops(graph, [{'op': 'expand_nodes_from_pattern', 'pattern': 'PLC[1..2]', 'node_type': 'computer'}])
    assert [node['id'] for node in patched['nodes']] == ['PLC1', 'PLC2']
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_stage_graphs.py tests/unit/test_patch_ops.py -v`
Expected: FAIL because skeleton helpers and range-aware patch ops do not exist.

- [ ] **Step 3: Write minimal implementation**

Implement `build_logical_skeleton()`, `build_physical_skeleton()`, and the first batch/range patch ops needed by the runtime. Keep the initial op surface minimal: one range-aware node expansion op and one batch update op are enough for v1.

- [ ] **Step 4: Run targeted tests to verify they pass**

Run: `pytest tests/unit/test_stage_graphs.py tests/unit/test_patch_ops.py -v`
Expected: PASS with no regressions in existing patch tests.

- [ ] **Step 5: Commit**

```bash
git add app/stage_graphs.py validators/patching.py tools/tgraph/ops/patch.py tests/unit/test_stage_graphs.py tests/unit/test_patch_ops.py
git commit -m "feat: add stage skeletons and batch patch ops"
```

### Task 4: Orchestrate `logical.check_author -> logical.graph_builder -> logical.repair`

**Files:**
- Modify: `app/stage_runtime.py`
- Modify: `agent/types.py`
- Modify: `stages/logical/guard.py`
- Modify: `stages/logical/spec.py`
- Modify: `artifacts/summarizer.py`
- Modify: `tests/unit/test_stage_runtime.py`
- Create: `tests/integration/test_patch_first_logical.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_stage_runtime_runs_logical_check_author_then_graph_builder() -> None:
    facade = FakeAgentFacade({'logical': [check_author_result, graph_builder_result]})
    runtime = StageRuntime(...)
    runtime.run_stage('logical')
    _, artifact = runtime.artifact_store.read_latest('logical', 'tgraph_logical')
    assert artifact['profile'] == 'logical.v1'
    assert artifact['nodes']


def test_logical_repair_round_receives_latest_graph_and_report() -> None:
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_stage_runtime.py tests/integration/test_patch_first_logical.py -v`
Expected: FAIL because current runtime assumes a single `LogicalOutput` containing a final graph.

- [ ] **Step 3: Write minimal implementation**

Refactor `StageRuntime.run_stage('logical')` to:
- build the skeleton
- call `logical.check_author`
- validate authored checkpoints/script
- call `logical.graph_builder`
- apply patch ops into a working graph
- persist the assembled final logical artifacts
- on failure, build repair context and call `logical.repair`

Add request-mode metadata to `AgentRequest` only if the message codec truly needs it; keep the request shape minimal.

- [ ] **Step 4: Run targeted tests to verify they pass**

Run: `pytest tests/unit/test_stage_runtime.py tests/integration/test_patch_first_logical.py -v`
Expected: PASS; failing cases should now be isolated to physical-stage assumptions.

- [ ] **Step 5: Commit**

```bash
git add app/stage_runtime.py agent/types.py stages/logical/guard.py stages/logical/spec.py artifacts/summarizer.py tests/unit/test_stage_runtime.py tests/integration/test_patch_first_logical.py
git commit -m "feat: add patch-first logical runtime"
```

## Chunk 3: Physical Patch-First Runtime and Boundary Rules

### Task 5: Combine logical and physical validation in a split physical stage

**Files:**
- Modify: `app/checkpoint_runner.py`
- Modify: `app/stage_runtime.py`
- Modify: `stages/physical/guard.py`
- Modify: `stages/physical/spec.py`
- Create: `tests/integration/test_patch_first_physical.py`
- Modify: `tests/integration/test_logical_to_physical.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_physical_validation_runs_logical_and_physical_checkpoints_together() -> None:
    ...
    assert report.ok is True
    assert 'logical.logical_checkpoints' in physical_request.inputs


def test_physical_stage_boundary_error_does_not_mutate_logical_links() -> None:
    with pytest.raises(StageRuntimeError, match='stage boundary'):
        runtime.run_stage('physical')
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_patch_first_physical.py tests/integration/test_logical_to_physical.py -v`
Expected: FAIL because physical validation currently uses only physical checkpoints and current runtime cannot classify boundary errors.

- [ ] **Step 3: Write minimal implementation**

Refactor physical orchestration to:
- run `physical.check_author`
- build a physical skeleton from passed `tgraph_logical`
- apply physical patch ops without changing logical connectivity
- validate using `logical_checkpoints + physical_checkpoints`
- raise a distinct stage-boundary failure when physical feasibility requires logical redesign

- [ ] **Step 4: Run targeted tests to verify they pass**

Run: `pytest tests/integration/test_patch_first_physical.py tests/integration/test_logical_to_physical.py tests/unit/test_stage_runtime.py -v`
Expected: PASS with physical boundary behavior covered.

- [ ] **Step 5: Commit**

```bash
git add app/checkpoint_runner.py app/stage_runtime.py stages/physical/guard.py stages/physical/spec.py tests/integration/test_patch_first_physical.py tests/integration/test_logical_to_physical.py tests/unit/test_stage_runtime.py
git commit -m "feat: add patch-first physical runtime"
```

## Chunk 4: Backend Selection, Prompts, and Regression Coverage

### Task 6: Respect config-driven backend selection and retire final-graph fixture assumptions

**Files:**
- Modify: `app/container.py`
- Modify: `tests/unit/test_agent_facade.py`
- Modify: `tests/unit/test_tplan_runner.py`
- Modify: `tests/integration/test_ground_to_logical.py`
- Modify: `README.md`
- Modify: `prompts/ground.md`
- Modify: `prompts/logical.md`
- Modify: `prompts/physical.md`

- [ ] **Step 1: Write the failing tests**

```python
def test_build_container_uses_langchain_facade_when_backend_is_langchain() -> None:
    container = build_container(root=tmp_path, config_dir=config_dir_with_langchain_backend)
    assert container.settings.agent_backend == 'langchain'
    assert isinstance(container.runner.stage_runtime.agent_facade, LangChainAgentFacade)
```

Also update `test_tplan_runner.py` and integration tests so fake fixtures represent round outputs instead of final graphs.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_agent_facade.py tests/unit/test_tplan_runner.py tests/integration/test_ground_to_logical.py -v`
Expected: FAIL because container still hard-wires `FakeAgentFacade(_default_fixtures())` and tests still assume final-graph fixtures.

- [ ] **Step 3: Write minimal implementation**

Use `settings.agent_backend` in `app/container.py` to choose fake vs LangChain-backed execution. Keep fake fixtures for tests/dev, but convert them to round-output fixtures that exercise the new runtime path. Update prompts so they describe the real stage roles and round modes instead of placeholders.

- [ ] **Step 4: Run targeted tests to verify they pass**

Run: `pytest tests/unit/test_agent_facade.py tests/unit/test_tplan_runner.py tests/integration/test_ground_to_logical.py -v`
Expected: PASS with config-driven backend selection and prompt/runtime contract alignment.

- [ ] **Step 5: Commit**

```bash
git add app/container.py tests/unit/test_agent_facade.py tests/unit/test_tplan_runner.py tests/integration/test_ground_to_logical.py README.md prompts/ground.md prompts/logical.md prompts/physical.md
git commit -m "feat: wire real three-stage backend selection"
```

### Task 7: Run end-to-end regression and clean up docs

**Files:**
- Modify: `README.md`
- Modify: any touched tests/docs from earlier tasks if verification exposes drift

- [ ] **Step 1: Run focused regression suites**

Run: `pytest tests/unit/test_constraint_refs.py tests/unit/test_stage_graphs.py tests/unit/test_stage_runtime.py tests/integration/test_patch_first_logical.py tests/integration/test_patch_first_physical.py -v`
Expected: PASS.

- [ ] **Step 2: Run broader runtime suites**

Run: `pytest tests/unit/test_tplan_runner.py tests/integration/test_ground_to_logical.py tests/integration/test_logical_to_physical.py -v`
Expected: PASS.

- [ ] **Step 3: Run the full test suite if the focused suites are green**

Run: `pytest -v`
Expected: PASS; if unrelated failures remain, capture them explicitly before any final summary.

- [ ] **Step 4: Update README language to describe the new runtime honestly**

Make sure README no longer claims default execution is fixture-returned final graphs, and document the patch-first round flow plus config-driven backend switch.

- [ ] **Step 5: Commit**

```bash
git add README.md tests/unit tests/integration prompts app stages validators tools
git commit -m "test: cover patch-first staged runtime"
```
