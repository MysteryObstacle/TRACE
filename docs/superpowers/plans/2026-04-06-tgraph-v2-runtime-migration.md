# TGraph v2 Runtime Migration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current function-oriented TGraph layer with a one-shot `TGraphJSON + TGraphRuntime + Transaction` migration, and wire logical/physical stages to the new runtime and tool protocol.

**Architecture:** Keep `TGraphJSON` as the artifact contract, but move normalization, validation, analysis, and mutation into a runtime object plus explicit transactions. Replace JSON-only helper paths with runtime-aware stage orchestration, and introduce a thin Agent/TGraph tool protocol instead of a second patch language.

**Tech Stack:** Python 3.10+, Pydantic, NetworkX, LangGraph, pytest

---

## File Map

- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/model.py`
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/derive.py`
- Delete or replace: `d:/Projects/Trace/src/trace/tools/tgraph/patch.py`
- Delete or replace: `d:/Projects/Trace/src/trace/tools/tgraph/query.py`
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/__init__.py`
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/validate/__init__.py`
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/validate/f1_format.py`
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/validate/f2_schema.py`
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/validate/f3_consistency.py`
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/validate/f4_intent.py`
- Create: `d:/Projects/Trace/src/trace/tools/tgraph/runtime.py`
- Create: `d:/Projects/Trace/src/trace/tools/tgraph/transaction.py`
- Create: `d:/Projects/Trace/src/trace/tools/tgraph/protocol.py`
- Modify: `d:/Projects/Trace/src/trace/stages/logical/prepare.py`
- Modify: `d:/Projects/Trace/src/trace/stages/logical/subgraph.py`
- Modify: `d:/Projects/Trace/src/trace/stages/logical/schemas.py`
- Modify: `d:/Projects/Trace/src/trace/stages/logical/validator.py`
- Modify: `d:/Projects/Trace/src/trace/stages/logical/prompts/builder.md`
- Modify: `d:/Projects/Trace/src/trace/stages/logical/prompts/repair.md`
- Modify: `d:/Projects/Trace/src/trace/stages/physical/prepare.py`
- Modify: `d:/Projects/Trace/src/trace/stages/physical/subgraph.py`
- Modify: `d:/Projects/Trace/src/trace/stages/physical/schemas.py`
- Modify: `d:/Projects/Trace/src/trace/stages/physical/validator.py`
- Modify: `d:/Projects/Trace/src/trace/stages/physical/prompts/builder.md`
- Modify: `d:/Projects/Trace/src/trace/stages/physical/prompts/repair.md`
- Modify: `d:/Projects/Trace/src/trace/runtime/role_client.py`
- Test: `d:/Projects/Trace/tests/unit/tools/tgraph/test_graph_core.py`
- Test: `d:/Projects/Trace/tests/unit/tools/tgraph/test_query.py`
- Test: `d:/Projects/Trace/tests/unit/config/test_prompts.py`
- Test: `d:/Projects/Trace/tests/integration/test_runtime_pipeline.py`

## Chunk 1: Runtime Core

### Task 1: Replace the old schema-only model with `TGraphJSON`

**Files:**
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/model.py`
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/__init__.py`
- Test: `d:/Projects/Trace/tests/unit/config/test_prompts.py`

- [ ] **Step 1: Write the failing schema compatibility test**

```python
from trace.tools.tgraph.model import TGraphJSON
from trace.stages.logical.schemas import LogicalArtifact
from trace.stages.physical.schemas import PhysicalArtifact


def test_stage_artifacts_use_tgraph_json_schema():
    assert LogicalArtifact.model_fields["tgraph_logical"].annotation is TGraphJSON
    assert PhysicalArtifact.model_fields["tgraph_physical"].annotation is TGraphJSON
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/config/test_prompts.py::test_stage_artifacts_use_tgraph_json_schema -v`
Expected: FAIL because the stage schemas still point at the old `TGraph` model.

- [ ] **Step 3: Replace the old schema model with `TGraphJSON` aliases and helpers**

```python
class TGraphJSON(BaseModel):
    profile: str
    nodes: list[NodeJSON] = Field(default_factory=list)
    links: list[LinkJSON] = Field(default_factory=list)


def ensure_tgraph_json(graph: TGraphJSON | dict[str, Any]) -> TGraphJSON:
    ...
```

- [ ] **Step 4: Update exports and schema imports**

```python
from trace.tools.tgraph.model import TGraphJSON
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/config/test_prompts.py::test_stage_artifacts_use_tgraph_json_schema -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/trace/tools/tgraph/model.py src/trace/tools/tgraph/__init__.py src/trace/stages/logical/schemas.py src/trace/stages/physical/schemas.py tests/unit/config/test_prompts.py
git commit -m "refactor: rename tgraph schema to tgraph json"
```

### Task 2: Add `TGraphRuntime` initialization and normalization

**Files:**
- Create: `d:/Projects/Trace/src/trace/tools/tgraph/runtime.py`
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/model.py`
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/derive.py`
- Test: `d:/Projects/Trace/tests/unit/tools/tgraph/test_graph_core.py`

- [ ] **Step 1: Write the failing runtime initialization test**

```python
from trace.tools.tgraph.runtime import TGraphRuntime


def test_runtime_from_json_normalizes_link_ids_and_infers_node_refs():
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "r1", "type": "router", "label": "r1", "ports": [{"id": "p2", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            {"id": "r2", "type": "router", "label": "r2", "ports": [{"id": "p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
        ],
        "links": [{"id": "p2--p1", "from_port": "p2", "to_port": "p1"}],
    }

    runtime = TGraphRuntime.from_json(graph)

    assert runtime.to_json()["links"][0]["id"] == "p1--p2"
    assert runtime.to_json()["links"][0]["from_node"] == "r2"
    assert runtime.to_json()["links"][0]["to_node"] == "r1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/tools/tgraph/test_graph_core.py::test_runtime_from_json_normalizes_link_ids_and_infers_node_refs -v`
Expected: FAIL because `TGraphRuntime` does not exist yet.

- [ ] **Step 3: Implement `TGraphRuntime.from_json()` and `to_json()`**

```python
class TGraphRuntime:
    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "TGraphRuntime":
        ...

    def to_json(self) -> dict[str, Any]:
        ...
```

- [ ] **Step 4: Move normalization into runtime-backed helpers**

```python
def normalize_tgraph_json(graph: TGraphJSON | dict[str, Any]) -> TGraphJSON:
    return TGraphJSON.model_validate(TGraphRuntime.from_json(graph).to_json())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/tools/tgraph/test_graph_core.py::test_runtime_from_json_normalizes_link_ids_and_infers_node_refs -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/trace/tools/tgraph/runtime.py src/trace/tools/tgraph/model.py src/trace/tools/tgraph/derive.py tests/unit/tools/tgraph/test_graph_core.py
git commit -m "feat: add tgraph runtime normalization"
```

### Task 3: Add transaction-based editing

**Files:**
- Create: `d:/Projects/Trace/src/trace/tools/tgraph/transaction.py`
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/runtime.py`
- Delete or replace: `d:/Projects/Trace/src/trace/tools/tgraph/patch.py`
- Test: `d:/Projects/Trace/tests/unit/tools/tgraph/test_graph_core.py`

- [ ] **Step 1: Write the failing transaction edit test**

```python
from trace.tools.tgraph.runtime import TGraphRuntime


def test_transaction_add_link_commits_when_f1_to_f3_pass():
    runtime = TGraphRuntime.from_json({
        "profile": "logical.v1",
        "nodes": [
            {"id": "r1", "type": "router", "label": "r1", "ports": [{"id": "p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            {"id": "r2", "type": "router", "label": "r2", "ports": [{"id": "p2", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
        ],
        "links": [],
    })

    tx = runtime.begin_transaction()
    tx.add_link("p1", "p2")
    result = tx.commit(levels=["f1", "f2", "f3"])

    assert result["ok"] is True
    assert runtime.to_json()["links"][0]["id"] == "p1--p2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/tools/tgraph/test_graph_core.py::test_transaction_add_link_commits_when_f1_to_f3_pass -v`
Expected: FAIL because transactions do not exist yet.

- [ ] **Step 3: Implement `Transaction` and runtime transaction entrypoint**

```python
class TGraphTransaction:
    def add_link(self, from_port: str, to_port: str) -> None:
        ...

    def commit(self, levels: list[str] | None = None) -> dict[str, Any]:
        ...
```

- [ ] **Step 4: Remove or replace `apply_patch_ops()` with transaction-backed editing**

```python
def apply_patch_ops(...):
    raise NotImplementedError("use TGraphRuntime transactions instead")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/tools/tgraph/test_graph_core.py::test_transaction_add_link_commits_when_f1_to_f3_pass -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/trace/tools/tgraph/runtime.py src/trace/tools/tgraph/transaction.py src/trace/tools/tgraph/patch.py tests/unit/tools/tgraph/test_graph_core.py
git commit -m "feat: add tgraph transaction editing"
```

## Chunk 2: Validation and Queries

### Task 4: Move validators onto runtime-aware semantics

**Files:**
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/validate/__init__.py`
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/validate/f1_format.py`
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/validate/f2_schema.py`
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/validate/f3_consistency.py`
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/validate/f4_intent.py`
- Test: `d:/Projects/Trace/tests/unit/tools/tgraph/test_graph_core.py`

- [ ] **Step 1: Write the failing consistency test for single-link-per-port**

```python
from trace.tools.tgraph.validate import run_default_validators


def test_validator_rejects_port_with_multiple_links():
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "r1", "type": "router", "label": "r1", "ports": [{"id": "p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            {"id": "r2", "type": "router", "label": "r2", "ports": [{"id": "p2", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            {"id": "r3", "type": "router", "label": "r3", "ports": [{"id": "p3", "ip": "10.0.0.3", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
        ],
        "links": [
            {"id": "p1--p2", "from_port": "p1", "to_port": "p2"},
            {"id": "p1--p3", "from_port": "p1", "to_port": "p3"},
        ],
    }

    report = run_default_validators(graph)

    assert report.ok is False
    assert any(issue.code == "port_degree_exceeded" for issue in report.issues)
```

- [ ] **Step 2: Run test to verify it fails or is brittle**

Run: `pytest tests/unit/tools/tgraph/test_graph_core.py::test_validator_rejects_port_with_multiple_links -v`
Expected: FAIL or rely on JSON-only assumptions that will be removed.

- [ ] **Step 3: Rework validator entrypoints to construct runtime state where appropriate**

```python
def run_default_validators(tgraph: dict, **kwargs) -> ValidationReport:
    ...
```

- [ ] **Step 4: Keep `f1 -> f2 -> f3 -> f4` contract while moving `f2/f3` onto runtime-aware checks**

```python
runtime = TGraphRuntime.from_json(tgraph)
```

- [ ] **Step 5: Run validator tests**

Run: `pytest tests/unit/tools/tgraph/test_graph_core.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/trace/tools/tgraph/validate tests/unit/tools/tgraph/test_graph_core.py
git commit -m "refactor: move tgraph validators onto runtime semantics"
```

### Task 5: Replace standalone query helpers with runtime methods

**Files:**
- Delete or replace: `d:/Projects/Trace/src/trace/tools/tgraph/query.py`
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/runtime.py`
- Test: `d:/Projects/Trace/tests/unit/tools/tgraph/test_query.py`

- [ ] **Step 1: Write the failing runtime query test**

```python
from trace.tools.tgraph.runtime import TGraphRuntime


def test_runtime_can_list_node_ids_and_neighbors():
    runtime = TGraphRuntime.from_json({
        "profile": "logical.v1",
        "nodes": [
            {"id": "r1", "type": "router", "label": "r1", "ports": [{"id": "p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            {"id": "r2", "type": "router", "label": "r2", "ports": [{"id": "p2", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
        ],
        "links": [{"id": "p1--p2", "from_port": "p1", "to_port": "p2"}],
    })

    assert runtime.list_nodes() == ["r1", "r2"]
    assert runtime.neighbors("r1") == ["r2"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/tools/tgraph/test_query.py::test_runtime_can_list_node_ids_and_neighbors -v`
Expected: FAIL because runtime query methods are not complete.

- [ ] **Step 3: Implement the minimal read/query methods on runtime**

```python
def list_nodes(self) -> list[str]:
    ...

def neighbors(self, node_id: str) -> list[str]:
    ...
```

- [ ] **Step 4: Remove or deprecate standalone `query.py`**

```python
from trace.tools.tgraph.runtime import TGraphRuntime
```

- [ ] **Step 5: Run query tests**

Run: `pytest tests/unit/tools/tgraph/test_query.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/trace/tools/tgraph/runtime.py src/trace/tools/tgraph/query.py tests/unit/tools/tgraph/test_query.py
git commit -m "refactor: move tgraph queries into runtime"
```

## Chunk 3: Stage Integration

### Task 6: Replace stage normalization and validation flows with runtime-backed logic

**Files:**
- Modify: `d:/Projects/Trace/src/trace/stages/logical/prepare.py`
- Modify: `d:/Projects/Trace/src/trace/stages/logical/subgraph.py`
- Modify: `d:/Projects/Trace/src/trace/stages/logical/validator.py`
- Modify: `d:/Projects/Trace/src/trace/stages/physical/prepare.py`
- Modify: `d:/Projects/Trace/src/trace/stages/physical/subgraph.py`
- Modify: `d:/Projects/Trace/src/trace/stages/physical/validator.py`
- Test: `d:/Projects/Trace/tests/integration/test_runtime_pipeline.py`

- [ ] **Step 1: Write the failing pipeline test for runtime-backed normalization**

```python
def test_runtime_pipeline_still_emits_json_artifacts(...):
    result = ...
    assert result["artifacts"]["logical"]["tgraph_logical"]["profile"] == "logical.v1"
    assert isinstance(result["artifacts"]["logical"]["tgraph_logical"]["nodes"], list)
```

- [ ] **Step 2: Run the focused pipeline test**

Run: `pytest tests/integration/test_runtime_pipeline.py -k tgraph -v`
Expected: FAIL once runtime-backed stage wiring begins.

- [ ] **Step 3: Replace `normalize_tgraph(...)` call sites with runtime-backed JSON round-trips**

```python
normalized = TGraphRuntime.from_json(artifact["tgraph_logical"]).to_json()
```

- [ ] **Step 4: Update stage validators to validate via runtime-aware helpers**

```python
report = validate_logical_artifact(state["draft_artifact"])
```

- [ ] **Step 5: Run integration tests**

Run: `pytest tests/integration/test_runtime_pipeline.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/trace/stages/logical src/trace/stages/physical tests/integration/test_runtime_pipeline.py
git commit -m "refactor: wire logical and physical stages to tgraph runtime"
```

### Task 7: Update prompt and schema contracts to describe runtime-backed editing

**Files:**
- Modify: `d:/Projects/Trace/src/trace/stages/logical/prompts/builder.md`
- Modify: `d:/Projects/Trace/src/trace/stages/logical/prompts/repair.md`
- Modify: `d:/Projects/Trace/src/trace/stages/physical/prompts/builder.md`
- Modify: `d:/Projects/Trace/src/trace/stages/physical/prompts/repair.md`
- Modify: `d:/Projects/Trace/src/trace/stages/logical/schemas.py`
- Modify: `d:/Projects/Trace/src/trace/stages/physical/schemas.py`
- Test: `d:/Projects/Trace/tests/unit/config/test_prompts.py`

- [ ] **Step 1: Write the failing prompt contract test**

```python
def test_logical_builder_prompt_requires_tgraph_json_shape():
    prompt = ...
    assert "tgraph_logical" in prompt
    assert "profile" in prompt
    assert "nodes" in prompt
    assert "links" in prompt
```

- [ ] **Step 2: Run prompt tests**

Run: `pytest tests/unit/config/test_prompts.py -v`
Expected: FAIL once schemas and prompt wording diverge.

- [ ] **Step 3: Update prompt wording to preserve JSON artifact shape while allowing runtime-backed internals**

```markdown
Keep `tgraph_logical` as a valid TGraphJSON with top-level fields `profile`, `nodes`, and `links`.
```

- [ ] **Step 4: Run prompt tests**

Run: `pytest tests/unit/config/test_prompts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/trace/stages/logical/prompts src/trace/stages/physical/prompts src/trace/stages/logical/schemas.py src/trace/stages/physical/schemas.py tests/unit/config/test_prompts.py
git commit -m "docs: update stage prompts for tgraph json and runtime migration"
```

## Chunk 4: Agent Tool Protocol

### Task 8: Add a thin Agent/TGraph protocol layer

**Files:**
- Create: `d:/Projects/Trace/src/trace/tools/tgraph/protocol.py`
- Modify: `d:/Projects/Trace/src/trace/runtime/role_client.py`
- Test: `d:/Projects/Trace/tests/unit/runtime/test_role_client.py`
- Test: `d:/Projects/Trace/tests/unit/tools/tgraph/test_graph_core.py`

- [ ] **Step 1: Write the failing protocol smoke test**

```python
from trace.tools.tgraph.protocol import tgraph_load, tgraph_begin_tx, tgraph_tx_apply, tgraph_tx_commit


def test_tgraph_protocol_commits_transaction():
    handle = tgraph_load({
        "profile": "logical.v1",
        "nodes": [
            {"id": "r1", "type": "router", "label": "r1", "ports": [{"id": "p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            {"id": "r2", "type": "router", "label": "r2", "ports": [{"id": "p2", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
        ],
        "links": [],
    })

    tx = tgraph_begin_tx(handle)
    tgraph_tx_apply(tx, "add_link", {"from_port": "p1", "to_port": "p2"})
    result = tgraph_tx_commit(tx, ["f1", "f2", "f3"])

    assert result["ok"] is True
```

- [ ] **Step 2: Run the protocol test to verify it fails**

Run: `pytest tests/unit/tools/tgraph/test_graph_core.py::test_tgraph_protocol_commits_transaction -v`
Expected: FAIL because the protocol layer does not exist.

- [ ] **Step 3: Implement the thin handle-based protocol**

```python
def tgraph_load(graph_json: dict) -> str:
    ...

def tgraph_tx_apply(tx_handle: str, op: str, args: dict | None = None) -> Any:
    ...
```

- [ ] **Step 4: Wire tool registration hooks into role execution without breaking structured-output roles**

```python
def invoke(..., tools: list[Any] | None = None) -> Any:
    ...
```

- [ ] **Step 5: Run focused protocol and runtime role tests**

Run: `pytest tests/unit/runtime/test_role_client.py tests/unit/tools/tgraph/test_graph_core.py -k "protocol or transaction" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/trace/tools/tgraph/protocol.py src/trace/runtime/role_client.py tests/unit/runtime/test_role_client.py tests/unit/tools/tgraph/test_graph_core.py
git commit -m "feat: add agent tgraph tool protocol"
```

## Chunk 5: Cleanup and Full Verification

### Task 9: Remove dead old-layer references and verify the one-shot migration

**Files:**
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/__init__.py`
- Modify: `d:/Projects/Trace/src/trace_core.egg-info/PKG-INFO`
- Test: `d:/Projects/Trace/tests/unit/tools/tgraph/test_graph_core.py`
- Test: `d:/Projects/Trace/tests/unit/tools/tgraph/test_query.py`
- Test: `d:/Projects/Trace/tests/unit/config/test_prompts.py`
- Test: `d:/Projects/Trace/tests/integration/test_runtime_pipeline.py`

- [ ] **Step 1: Remove remaining imports or docs that reference the deleted old-layer API**

```python
__all__ = ["TGraphJSON", "TGraphRuntime", "TGraphTransaction"]
```

- [ ] **Step 2: Run the focused unit suite**

Run: `pytest tests/unit/tools/tgraph tests/unit/config/test_prompts.py tests/unit/runtime/test_role_client.py -v`
Expected: PASS

- [ ] **Step 3: Run the integration pipeline suite**

Run: `pytest tests/integration/test_runtime_pipeline.py -v`
Expected: PASS

- [ ] **Step 4: Run the full test suite**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/trace/tools/tgraph src/trace/stages/logical src/trace/stages/physical src/trace/runtime/role_client.py tests
git commit -m "refactor: complete one-shot tgraph runtime migration"
```
