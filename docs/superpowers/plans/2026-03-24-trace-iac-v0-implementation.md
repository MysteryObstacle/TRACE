# TRACE IaC v0 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first end-to-end TRACE runtime that can execute `ground -> logical -> physical -> translate_stub`, persist stage artifacts, run logical and physical validation/repair loops, and expose LangSmith-ready tracing hooks.

**Architecture:** Start with an artifact-first runtime and fake agent fixtures so the control flow is testable before any real model behavior is introduced. Once the deterministic flow is stable, add the LangChain adapter, LangSmith tracing wrapper, and thin tool/stage prompt scaffolding without expanding scope into real translation.

**Tech Stack:** Python 3.10+, Typer, Pydantic v2, LangChain, LangGraph, LangSmith, PyYAML, orjson, pytest, pytest-asyncio

---

## File Map

### Files to create

- `main.py`
- `pyproject.toml`
- `.env.example`
- `README.md`
- `configs/app.yaml`
- `configs/model.yaml`
- `configs/stages/ground.yaml`
- `configs/stages/logical.yaml`
- `configs/stages/physical.yaml`
- `prompts/ground.md`
- `prompts/logical.md`
- `prompts/physical.md`
- `app/__init__.py`
- `app/container.py`
- `app/contracts.py`
- `app/state.py`
- `app/tplan_runner.py`
- `app/stage_runtime.py`
- `app/checkpoint_runner.py`
- `app/transition_policy.py`
- `app/checkpoints.py`
- `app/errors.py`
- `stages/__init__.py`
- `stages/registry.py`
- `stages/ground/__init__.py`
- `stages/ground/spec.py`
- `stages/ground/output_schema.py`
- `stages/ground/normalize.py`
- `stages/ground/guard.py`
- `stages/logical/__init__.py`
- `stages/logical/spec.py`
- `stages/logical/output_schema.py`
- `stages/logical/guard.py`
- `stages/physical/__init__.py`
- `stages/physical/spec.py`
- `stages/physical/output_schema.py`
- `stages/physical/guard.py`
- `agent/__init__.py`
- `agent/facade.py`
- `agent/ports.py`
- `agent/types.py`
- `agent/policies.py`
- `agent/langchain/__init__.py`
- `agent/langchain/engine.py`
- `agent/langchain/model_factory.py`
- `agent/langchain/message_codec.py`
- `agent/langchain/tracing.py`
- `artifacts/__init__.py`
- `artifacts/models.py`
- `artifacts/store.py`
- `artifacts/selectors.py`
- `artifacts/summarizer.py`
- `validators/__init__.py`
- `validators/report.py`
- `validators/tgraph_runner.py`
- `validators/patching.py`
- `tools/__init__.py`
- `tools/registry.py`
- `tools/policy.py`
- `tools/knowledge/__init__.py`
- `tools/knowledge/list_topics.py`
- `tools/knowledge/read_doc.py`
- `tools/knowledge/search.py`
- `tools/tgraph/__init__.py`
- `tools/tgraph/model/__init__.py`
- `tools/tgraph/model/tgraph.py`
- `tools/tgraph/model/node.py`
- `tools/tgraph/model/edge.py`
- `tools/tgraph/ops/__init__.py`
- `tools/tgraph/ops/materialize.py`
- `tools/tgraph/ops/patch.py`
- `tools/tgraph/ops/serialize.py`
- `tools/tgraph/validate/__init__.py`
- `tools/tgraph/validate/f1_format.py`
- `tools/tgraph/validate/f2_schema.py`
- `tools/tgraph/validate/f3_consistency.py`
- `tools/tgraph/validate/f4_intent.py`
- `tests/unit/test_contracts.py`
- `tests/unit/test_stage_runtime.py`
- `tests/unit/test_tplan_runner.py`
- `tests/unit/test_agent_facade.py`
- `tests/unit/test_tool_policy.py`
- `tests/unit/test_checkpoint_runner.py`
- `tests/unit/test_ground_normalize.py`
- `tests/unit/test_artifact_store.py`
- `tests/unit/test_artifact_selectors.py`
- `tests/unit/test_patch_ops.py`
- `tests/integration/test_ground_to_logical.py`
- `tests/integration/test_logical_to_physical.py`
- `tests/e2e/test_cli_run.py`

### Files to modify later in the plan

- [docs/superpowers/specs/2026-03-24-trace-iac-v0-design.md](/d:/Paper/10.Domain%20Agent/Trace/docs/superpowers/specs/2026-03-24-trace-iac-v0-design.md) only if implementation uncovers a spec mismatch

### Responsibility notes

- `app/` owns orchestration and checkpoint lifecycle only.
- `stages/` owns stage-specific contracts and guards only.
- `agent/` hides LangChain and tracing details from the runtime.
- `artifacts/` owns versioned artifact persistence and large-graph summaries.
- `validators/` owns checkpoint execution, report normalization, and patch application.
- `tools/` stays intentionally thin in v0 and should not expand beyond placeholders until the runtime works end to end.

## Implementation order

1. Bootstrap the project and deterministic contracts.
2. Make `ground -> logical -> physical` run end to end with a fake agent.
3. Add validation, patching, and resume behavior.
4. Add LangChain and LangSmith adapters behind stable ports.
5. Only then refine tools, prompts, and stage behavior.

## Chunk 1: Bootstrap the runtime skeleton

### Task 1: Create project metadata and package layout

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `README.md`
- Create: `main.py`
- Create: `app/__init__.py`
- Create: `stages/__init__.py`
- Create: `agent/__init__.py`
- Create: `artifacts/__init__.py`
- Create: `validators/__init__.py`
- Create: `tools/__init__.py`
- Test: `tests/e2e/test_cli_run.py`

- [ ] **Step 1: Write the failing CLI smoke test**

```python
from typer.testing import CliRunner

from main import app


def test_run_command_shows_help():
    runner = CliRunner()
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/e2e/test_cli_run.py::test_run_command_shows_help -v`
Expected: FAIL with import error because `main.py` does not exist yet

- [ ] **Step 3: Write minimal project metadata and CLI shell**

```python
import typer

app = typer.Typer()


@app.command()
def run() -> None:
    raise typer.Exit()
```

- [ ] **Step 4: Add dependencies and package configuration**

```toml
[project]
name = "trace-iac"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "langchain==1.2.12",
  "langgraph==1.0.10",
  "langchain-openai==1.1.11",
  "pydantic>=2.12,<2.14",
  "pydantic-settings>=2.10,<3.0",
  "typer==0.24.1",
  "rich>=14.0,<15.0",
  "PyYAML>=6.0,<7.0",
  "orjson==3.11.7",
  "tenacity>=9.0,<10.0",
  "httpx>=0.28,<1.0",
]
```

- [ ] **Step 5: Run the smoke test again**

Run: `pytest tests/e2e/test_cli_run.py::test_run_command_shows_help -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .env.example README.md main.py app stages agent artifacts validators tools tests/e2e/test_cli_run.py
git commit -m "chore: bootstrap trace runtime package"
```

### Task 2: Add core contracts and serialization tests

**Files:**
- Create: `app/contracts.py`
- Create: `app/state.py`
- Create: `validators/report.py`
- Create: `tests/unit/test_contracts.py`

- [ ] **Step 1: Write failing contract tests**

```python
from app.contracts import ArtifactSelector, ValidationIssue


def test_artifact_selector_round_trips():
    selector = ArtifactSelector(stage="ground", name="expanded_node_ids")
    payload = selector.model_dump()
    assert payload["stage"] == "ground"


def test_validation_issue_defaults_are_stable():
    issue = ValidationIssue(
        code="schema_error",
        message="missing node",
        severity="error",
        scope="topology",
    )
    assert issue.targets == []
    assert issue.json_paths == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_contracts.py -v`
Expected: FAIL with import error because contract modules do not exist yet

- [ ] **Step 3: Implement the shared models**

```python
class ArtifactSelector(BaseModel):
    stage: Literal["ground", "logical", "physical"]
    name: str
    required: bool = True
```

- [ ] **Step 4: Add `RunState`, `ArtifactRef`, `StageSpec`, `ValidationIssue`, and `ValidationReport`**

```python
class RunState(BaseModel):
    run_id: str
    session_id: str
    current_stage: str | None = None
    status: Literal["running", "failed", "completed"]
```

- [ ] **Step 5: Run contract tests**

Run: `pytest tests/unit/test_contracts.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/contracts.py app/state.py validators/report.py tests/unit/test_contracts.py
git commit -m "feat: add runtime contracts"
```

### Task 3: Register stage schemas and normalization boundaries

**Files:**
- Create: `stages/registry.py`
- Create: `stages/ground/output_schema.py`
- Create: `stages/ground/spec.py`
- Create: `stages/ground/normalize.py`
- Create: `stages/ground/guard.py`
- Create: `stages/logical/output_schema.py`
- Create: `stages/logical/spec.py`
- Create: `stages/logical/guard.py`
- Create: `stages/physical/output_schema.py`
- Create: `stages/physical/spec.py`
- Create: `stages/physical/guard.py`
- Create: `tests/unit/test_ground_normalize.py`

- [ ] **Step 1: Write failing normalization tests**

```python
from stages.ground.normalize import expand_node_patterns


def test_expand_node_patterns_handles_ranges_and_literals():
    result = expand_node_patterns(["PLC[1..3]", "HMI1"])
    assert result == ["PLC1", "PLC2", "PLC3", "HMI1"]
```

- [ ] **Step 2: Run the normalization test to verify it fails**

Run: `pytest tests/unit/test_ground_normalize.py -v`
Expected: FAIL because the normalization module does not exist yet

- [ ] **Step 3: Add output schema models for ground, logical, and physical**

```python
class ConstraintItem(BaseModel):
    id: str
    scope: Literal["node_ids", "topology"]
    targets: list[str] = Field(default_factory=list)
    text: str
```

- [ ] **Step 4: Implement `expand_node_patterns()` and stage specs**

```python
def expand_node_patterns(patterns: list[str]) -> list[str]:
    ...
```

- [ ] **Step 5: Register the stages in `stages/registry.py`**

```python
STAGE_ORDER = ["ground", "logical", "physical"]
```

- [ ] **Step 6: Run the stage schema tests**

Run: `pytest tests/unit/test_ground_normalize.py tests/unit/test_contracts.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add stages tests/unit/test_ground_normalize.py
git commit -m "feat: add stage schemas and normalization"
```

## Chunk 2: Make the three-stage flow run with fake agents

### Task 4: Implement artifact persistence and selector resolution

**Files:**
- Create: `artifacts/models.py`
- Create: `artifacts/store.py`
- Create: `artifacts/selectors.py`
- Create: `app/checkpoints.py`
- Create: `tests/unit/test_artifact_store.py`
- Create: `tests/unit/test_artifact_selectors.py`

- [ ] **Step 1: Write failing artifact store tests**

```python
def test_store_writes_incrementing_versions(tmp_path):
    store = ArtifactStore(tmp_path)
    first = store.write(stage="ground", name="expanded_node_ids", data=["PLC1"])
    second = store.write(stage="ground", name="expanded_node_ids", data=["PLC1", "PLC2"])
    assert first.version == 1
    assert second.version == 2
```

- [ ] **Step 2: Run the artifact tests to verify they fail**

Run: `pytest tests/unit/test_artifact_store.py tests/unit/test_artifact_selectors.py -v`
Expected: FAIL with missing imports

- [ ] **Step 3: Implement `ArtifactStore` and versioned artifact metadata**

```python
class ArtifactStore:
    def write(self, stage: str, name: str, data: Any) -> ArtifactRef:
        ...
```

- [ ] **Step 4: Implement selector resolution by latest version**

```python
def resolve_inputs(store: ArtifactStore, selectors: list[ArtifactSelector]) -> dict[str, Any]:
    ...
```

- [ ] **Step 5: Add checkpoint snapshot writing**

```python
def write_checkpoint(path: Path, payload: dict[str, Any]) -> Path:
    ...
```

- [ ] **Step 6: Run the artifact tests**

Run: `pytest tests/unit/test_artifact_store.py tests/unit/test_artifact_selectors.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add artifacts app/checkpoints.py tests/unit/test_artifact_store.py tests/unit/test_artifact_selectors.py
git commit -m "feat: add artifact persistence and checkpoint storage"
```

### Task 5: Implement the fake agent facade and stage runtime

**Files:**
- Create: `agent/ports.py`
- Create: `agent/types.py`
- Create: `agent/policies.py`
- Create: `agent/facade.py`
- Create: `app/errors.py`
- Create: `app/stage_runtime.py`
- Create: `tests/unit/test_agent_facade.py`
- Create: `tests/unit/test_stage_runtime.py`

- [ ] **Step 1: Write failing fake agent and stage runtime tests**

```python
def test_stage_runtime_passes_declared_artifacts_to_agent(fake_runtime):
    result = fake_runtime.run_stage("logical")
    assert result.stage_id == "logical"
    assert "ground.expanded_node_ids" in result.inputs
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_agent_facade.py tests/unit/test_stage_runtime.py -v`
Expected: FAIL because the facade and runtime do not exist yet

- [ ] **Step 3: Define `ReasonerPort` and request/response models**

```python
class AgentRequest(BaseModel):
    stage_id: str
    prompt: str
    inputs: dict[str, Any]
```

- [ ] **Step 4: Implement `FakeAgentFacade` and `StageRuntime`**

```python
class FakeAgentFacade:
    def invoke(self, request: AgentRequest) -> AgentResult:
        return self.fixtures[request.stage_id]
```

- [ ] **Step 5: Persist stage outputs to the artifact store and run stage guards**

```python
stage_output = facade.invoke(request)
artifact_store.write(...)
guard.assert_valid(...)
```

- [ ] **Step 6: Run runtime unit tests**

Run: `pytest tests/unit/test_agent_facade.py tests/unit/test_stage_runtime.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add agent app/errors.py app/stage_runtime.py tests/unit/test_agent_facade.py tests/unit/test_stage_runtime.py
git commit -m "feat: add fake agent facade and stage runtime"
```

### Task 6: Implement the full runner and CLI `run`/`resume`

**Files:**
- Create: `app/container.py`
- Create: `app/tplan_runner.py`
- Create: `app/transition_policy.py`
- Modify: `main.py`
- Create: `tests/unit/test_tplan_runner.py`
- Modify: `tests/e2e/test_cli_run.py`

- [ ] **Step 1: Write failing runner tests**

```python
def test_runner_executes_three_stages_in_order(fake_container):
    result = fake_container.runner.run("user intent")
    assert result.status == "completed"
    assert result.stage_history == ["ground", "logical", "physical"]
```

- [ ] **Step 2: Run runner tests to verify they fail**

Run: `pytest tests/unit/test_tplan_runner.py tests/e2e/test_cli_run.py -v`
Expected: FAIL because the runner and CLI commands are incomplete

- [ ] **Step 3: Implement `TPlanRunner` with a `translate_stub()` tail**

```python
for stage_id in ["ground", "logical", "physical"]:
    stage_runtime.run(stage_id, run_state)
translate_stub(run_state)
```

- [ ] **Step 4: Implement the dependency container and CLI commands**

```python
@app.command()
def run(intent: str) -> None:
    ...


@app.command()
def resume(run_id: str) -> None:
    ...
```

- [ ] **Step 5: Run the runner and CLI tests**

Run: `pytest tests/unit/test_tplan_runner.py tests/e2e/test_cli_run.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/container.py app/tplan_runner.py app/transition_policy.py main.py tests/unit/test_tplan_runner.py tests/e2e/test_cli_run.py
git commit -m "feat: wire three-stage runner and cli"
```

## Chunk 3: Add validation, repair, and resume mechanics

### Task 7: Implement validation reports and checkpoint execution

**Files:**
- Create: `app/checkpoint_runner.py`
- Create: `validators/tgraph_runner.py`
- Create: `tests/unit/test_checkpoint_runner.py`

- [ ] **Step 1: Write the failing checkpoint runner tests**

```python
def test_checkpoint_runner_executes_builtin_function(tmp_path):
    report = run_checkpoints(
        tgraph={"nodes": [], "edges": []},
        checkpoints=[{"id": "c1", "function_name": "f1_format", "input_params": {}}],
    )
    assert report.ok is True
```

- [ ] **Step 2: Run the checkpoint tests to verify they fail**

Run: `pytest tests/unit/test_checkpoint_runner.py -v`
Expected: FAIL because the runner does not exist yet

- [ ] **Step 3: Implement builtin validator dispatch**

```python
BUILTIN_VALIDATORS = {"f1_format": f1_format}
```

- [ ] **Step 4: Implement script loading and function invocation**

```python
spec = importlib.util.spec_from_file_location("validator_mod", script_path)
```

- [ ] **Step 5: Normalize results into `ValidationReport`**

```python
return ValidationReport(ok=not errors, issues=issues)
```

- [ ] **Step 6: Run checkpoint tests**

Run: `pytest tests/unit/test_checkpoint_runner.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/checkpoint_runner.py validators/tgraph_runner.py tests/unit/test_checkpoint_runner.py
git commit -m "feat: add checkpoint execution pipeline"
```

### Task 8: Add patch application and repair-context summarization

**Files:**
- Create: `validators/patching.py`
- Create: `artifacts/summarizer.py`
- Create: `tests/unit/test_patch_ops.py`

- [ ] **Step 1: Write failing patch tests**

```python
def test_add_node_patch_updates_tgraph():
    graph = {"nodes": [], "edges": []}
    updated = apply_patch_ops(graph, [{"op": "add_node", "value": {"id": "PLC1"}}])
    assert updated["nodes"] == [{"id": "PLC1"}]
```

- [ ] **Step 2: Run the patch tests to verify they fail**

Run: `pytest tests/unit/test_patch_ops.py -v`
Expected: FAIL because patching helpers do not exist yet

- [ ] **Step 3: Implement `GraphPatchOp` support in `validators/patching.py`**

```python
def apply_patch_ops(graph: dict[str, Any], ops: list[GraphPatchOp]) -> dict[str, Any]:
    ...
```

- [ ] **Step 4: Implement summary extraction for large graphs**

```python
def build_repair_context(graph: dict[str, Any], report: ValidationReport) -> dict[str, Any]:
    ...
```

- [ ] **Step 5: Run the patch tests**

Run: `pytest tests/unit/test_patch_ops.py tests/unit/test_checkpoint_runner.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add validators/patching.py artifacts/summarizer.py tests/unit/test_patch_ops.py
git commit -m "feat: add graph patching and repair summaries"
```

### Task 9: Wire validation, repair retries, and resume state into the runner

**Files:**
- Modify: `app/stage_runtime.py`
- Modify: `app/tplan_runner.py`
- Modify: `app/state.py`
- Modify: `app/checkpoints.py`
- Create: `tests/integration/test_ground_to_logical.py`
- Create: `tests/integration/test_logical_to_physical.py`

- [ ] **Step 1: Write failing integration tests for repair and resume**

```python
def test_logical_stage_retries_after_validation_failure(fake_app):
    result = fake_app.run("intent")
    assert result.status == "completed"
    assert result.validation_attempts["logical"] == 2
```

- [ ] **Step 2: Run integration tests to verify they fail**

Run: `pytest tests/integration/test_ground_to_logical.py tests/integration/test_logical_to_physical.py -v`
Expected: FAIL because repair and resume behavior is not wired yet

- [ ] **Step 3: Add repair-mode loops to `StageRuntime` for logical and physical**

```python
while attempt <= spec.max_rounds:
    output = facade.invoke(request)
    report = checkpoint_runner.run(...)
    if report.ok:
        break
```

- [ ] **Step 4: Persist numbered checkpoints and timeline events for each retry**

```python
timeline.append({"stage": stage_id, "attempt": attempt, "event": "validation_failed"})
```

- [ ] **Step 5: Add `resume` support from latest checkpoint and selected stage**

```python
runner.resume(run_id=run_id, from_stage=None)
```

- [ ] **Step 6: Run integration tests**

Run: `pytest tests/integration/test_ground_to_logical.py tests/integration/test_logical_to_physical.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/stage_runtime.py app/tplan_runner.py app/state.py app/checkpoints.py tests/integration/test_ground_to_logical.py tests/integration/test_logical_to_physical.py
git commit -m "feat: add repair loop and resume support"
```

## Chunk 4: Add LangChain, tracing, and thin tool scaffolding

### Task 10: Add the LangChain adapter behind stable ports

**Files:**
- Create: `agent/langchain/engine.py`
- Create: `agent/langchain/model_factory.py`
- Create: `agent/langchain/message_codec.py`
- Modify: `agent/facade.py`
- Modify: `agent/ports.py`
- Modify: `tests/unit/test_agent_facade.py`

- [ ] **Step 1: Write a failing adapter test**

```python
def test_langchain_facade_converts_request_to_messages(fake_model):
    ...
```

- [ ] **Step 2: Run adapter tests to verify they fail**

Run: `pytest tests/unit/test_agent_facade.py -v`
Expected: FAIL because the adapter is not implemented yet

- [ ] **Step 3: Implement the message codec and engine wrapper**

```python
def build_messages(request: AgentRequest) -> list[BaseMessage]:
    ...
```

- [ ] **Step 4: Keep `FakeAgentFacade` as the default test path and swap real engine by config**

```python
if settings.agent_backend == "fake":
    return FakeAgentFacade(...)
return LangChainAgentFacade(...)
```

- [ ] **Step 5: Run adapter tests**

Run: `pytest tests/unit/test_agent_facade.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add agent/langchain agent/facade.py agent/ports.py tests/unit/test_agent_facade.py
git commit -m "feat: add langchain adapter behind agent facade"
```

### Task 11: Add LangSmith tracing wrappers and configuration loading

**Files:**
- Create: `agent/langchain/tracing.py`
- Create: `configs/app.yaml`
- Create: `configs/model.yaml`
- Create: `configs/stages/ground.yaml`
- Create: `configs/stages/logical.yaml`
- Create: `configs/stages/physical.yaml`
- Modify: `app/container.py`
- Modify: `app/tplan_runner.py`
- Modify: `app/stage_runtime.py`

- [ ] **Step 1: Write a failing tracing/config test**

```python
def test_container_builds_tracing_client_when_enabled(tmp_path):
    ...
```

- [ ] **Step 2: Run tracing/config tests to verify they fail**

Run: `pytest tests/unit/test_tplan_runner.py tests/unit/test_stage_runtime.py -v`
Expected: FAIL because tracing/config plumbing is still missing

- [ ] **Step 3: Implement config loading from YAML and environment**

```python
class AppSettings(BaseSettings):
    langsmith_enabled: bool = False
```

- [ ] **Step 4: Implement tracing helpers for root runs, stage runs, validation runs, and patch runs**

```python
with tracer.stage_run(stage_id="logical", attempt=1):
    ...
```

- [ ] **Step 5: Run runtime tests**

Run: `pytest tests/unit/test_tplan_runner.py tests/unit/test_stage_runtime.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add agent/langchain/tracing.py configs app/container.py app/tplan_runner.py app/stage_runtime.py
git commit -m "feat: add config loading and langsmith tracing hooks"
```

### Task 12: Add thin v0 tool and prompt scaffolding without expanding scope

**Files:**
- Create: `tools/registry.py`
- Create: `tools/policy.py`
- Create: `tools/knowledge/list_topics.py`
- Create: `tools/knowledge/read_doc.py`
- Create: `tools/knowledge/search.py`
- Create: `tools/tgraph/model/tgraph.py`
- Create: `tools/tgraph/model/node.py`
- Create: `tools/tgraph/model/edge.py`
- Create: `tools/tgraph/ops/materialize.py`
- Create: `tools/tgraph/ops/patch.py`
- Create: `tools/tgraph/ops/serialize.py`
- Create: `tools/tgraph/validate/f1_format.py`
- Create: `tools/tgraph/validate/f2_schema.py`
- Create: `tools/tgraph/validate/f3_consistency.py`
- Create: `tools/tgraph/validate/f4_intent.py`
- Create: `prompts/ground.md`
- Create: `prompts/logical.md`
- Create: `prompts/physical.md`
- Create: `tests/unit/test_tool_policy.py`

- [ ] **Step 1: Write failing tool-policy tests**

```python
def test_logical_stage_only_sees_allowed_tools():
    registry = build_tool_registry()
    tools = filter_tools_for_stage("logical", registry)
    assert "search" in tools
```

- [ ] **Step 2: Run tool-policy tests to verify they fail**

Run: `pytest tests/unit/test_tool_policy.py -v`
Expected: FAIL because tool scaffolding does not exist yet

- [ ] **Step 3: Implement a minimal tool registry and stage allowlist**

```python
STAGE_TOOL_MAP = {
    "ground": ["search", "read_doc"],
    "logical": ["search", "read_doc"],
    "physical": ["search", "read_doc"],
}
```

- [ ] **Step 4: Add placeholder prompts and stub validator functions**

```python
def f1_format(tgraph: dict, **kwargs) -> list[dict]:
    return []
```

- [ ] **Step 5: Run tool-policy tests and the fast unit suite**

Run: `pytest tests/unit/test_tool_policy.py tests/unit/test_checkpoint_runner.py tests/unit/test_stage_runtime.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tools prompts tests/unit/test_tool_policy.py
git commit -m "feat: add v0 tool policy and prompt scaffolding"
```

## Final verification pass

### Task 13: Run the full local verification suite and document the happy path

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a short README quickstart**

```md
## Quickstart

python -m venv .venv
pip install -e .[dev]
pytest
python main.py run "PLC[1..2] with HMI1"
```

- [ ] **Step 2: Run the full test suite**

Run: `pytest`
Expected: PASS

- [ ] **Step 3: Run a manual CLI smoke test**

Run: `python main.py run "PLC[1..2] with HMI1"`
Expected: PASS and a new `runs/<run_id>/` directory containing `state.json`, artifacts, and checkpoints

- [ ] **Step 4: Run a manual resume smoke test**

Run: `python main.py resume <run_id>`
Expected: PASS and the runner resumes from the saved checkpoint state

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add runtime quickstart"
```

## Notes for execution

- Keep the fake agent path working throughout the whole plan. Do not force the real LangChain backend before the deterministic tests pass.
- Do not build real translation logic in this plan. `translate_stub()` should remain a no-op with trace and log hooks only.
- Generated validator scripts are part of runtime artifacts, not source-controlled modules.
- If implementation reveals a spec mismatch, update the spec first, then continue.
- Prioritize deterministic tests and small commits over broad scaffolding.

