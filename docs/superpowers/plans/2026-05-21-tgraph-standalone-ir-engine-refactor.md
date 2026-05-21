# TGraph Standalone IR Engine Refactor Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone `tgraph` IR engine package that provides graph IR, inspection, batch patching, validation, IO, target placeholders, CLI wrappers, and agent protocols while keeping TRACE's existing workflows working through compatibility adapters.

**Architecture:** Add a new `src/tgraph` package with clean boundaries: `core`, `operations`, `io`, `targets`, `agent`, and `cli`. Keep `src/trace/tools/tgraph` as the TRACE-facing compatibility layer during migration. Do not move TRACE workflow, knowledge catalogs, image catalogs, or LangGraph state into TGraph.

**Tech Stack:** Python 3.10+, Pydantic v2, Typer, pytest, existing TRACE test conventions.

---

## Scope Notes

This plan implements the phase-one IR engine only.

Do not implement real Terraform, Pulumi, or TOSCA generation. Target emitters should return stable `target_not_implemented` results.

Do not add `schema_version`, `profile`, or top-level `metadata` to the new canonical TGraph document. The phase-one canonical document is:

```json
{
  "stage": "logical",
  "nodes": [],
  "links": []
}
```

Do not move knowledge bases, image catalogs, scenario patterns, or workflow orchestration into `tgraph`.

## File Structure Map

Create:

- `src/tgraph/__init__.py`: small public API surface.
- `src/tgraph/core/__init__.py`: core exports.
- `src/tgraph/core/graph.py`: `TGraph`, `Node`, `Port`, `Link`, `ImageSpec`, `FlavorSpec`.
- `src/tgraph/core/stage.py`: `GraphStage` type and parsing helper.
- `src/tgraph/core/normalize.py`: canonical ordering and link normalization.
- `src/tgraph/core/errors.py`: core error model.
- `src/tgraph/io/__init__.py`: IO exports.
- `src/tgraph/io/json.py`: load/dump stable TGraph JSON.
- `src/tgraph/io/document.py`: document parse/dump helpers and top-level field policy.
- `src/tgraph/operations/__init__.py`: operation exports.
- `src/tgraph/operations/inspect/__init__.py`: inspection exports.
- `src/tgraph/operations/inspect/summary.py`: topology summary.
- `src/tgraph/operations/inspect/nodes.py`: node lookup and filtering.
- `src/tgraph/operations/inspect/ports.py`: port lookup and ownership.
- `src/tgraph/operations/inspect/links.py`: link lookup and adjacency.
- `src/tgraph/operations/inspect/paths.py`: reachability and path queries.
- `src/tgraph/operations/inspect/segments.py`: segment view when derivable.
- `src/tgraph/operations/patch/__init__.py`: patch exports.
- `src/tgraph/operations/patch/schema.py`: patch operation Pydantic models.
- `src/tgraph/operations/patch/apply.py`: atomic batch patch application.
- `src/tgraph/operations/patch/diff.py`: graph diff model.
- `src/tgraph/operations/patch/result.py`: patch result model.
- `src/tgraph/operations/patch/errors.py`: patch error model.
- `src/tgraph/operations/validate/__init__.py`: validation exports.
- `src/tgraph/operations/validate/issues.py`: validation issue and report models.
- `src/tgraph/operations/validate/policy.py`: validation levels and stage policy.
- `src/tgraph/operations/validate/runner.py`: `validate_document` and `validate_graph`.
- `src/tgraph/operations/validate/f1_format.py`: raw document validation.
- `src/tgraph/operations/validate/f2_schema.py`: schema validation.
- `src/tgraph/operations/validate/f3_graph.py`: graph consistency validation.
- `src/tgraph/operations/validate/f4_intent.py`: caller context validation.
- `src/tgraph/targets/__init__.py`: target exports.
- `src/tgraph/targets/base.py`: `TargetEmitter` protocol and options.
- `src/tgraph/targets/result.py`: emit result and output bundle model.
- `src/tgraph/targets/registry.py`: target registry.
- `src/tgraph/targets/terraform.py`: placeholder emitter.
- `src/tgraph/targets/pulumi.py`: placeholder emitter.
- `src/tgraph/targets/tosca.py`: placeholder emitter.
- `src/tgraph/agent/__init__.py`: agent protocol package.
- `src/tgraph/agent/protocol.py`: machine-readable protocol models.
- `src/tgraph/agent/schemas/tgraph.schema.json`: generated or hand-maintained schema.
- `src/tgraph/agent/schemas/patch.schema.json`: patch schema.
- `src/tgraph/agent/schemas/validation-report.schema.json`: validation schema.
- `src/tgraph/agent/schemas/inspect-result.schema.json`: inspect schema.
- `src/tgraph/agent/playbooks/repair.md`: repair loop guide.
- `src/tgraph/agent/playbooks/authoring.md`: graph authoring guide.
- `src/tgraph/agent/playbooks/validation.md`: validation guide.
- `src/tgraph/agent/playbooks/emission.md`: target emission guide.
- `src/tgraph/cli/__init__.py`: CLI package.
- `src/tgraph/cli/main.py`: Typer app for `tgraph`.
- `tests/unit/tgraph/core/test_graph.py`: core model tests.
- `tests/unit/tgraph/core/test_normalize.py`: normalization tests.
- `tests/unit/tgraph/io/test_json.py`: IO tests.
- `tests/unit/tgraph/operations/test_inspect.py`: inspect tests.
- `tests/unit/tgraph/operations/test_patch.py`: patch tests.
- `tests/unit/tgraph/operations/test_validate.py`: validation tests.
- `tests/unit/tgraph/targets/test_registry.py`: target placeholder tests.
- `tests/unit/tgraph/agent/test_schemas.py`: schema file tests.
- `tests/unit/tgraph/cli/test_cli.py`: CLI tests.

Modify:

- `pyproject.toml`: add `tgraph = "tgraph.cli.main:app"` console script.
- `src/trace/tools/tgraph/__init__.py`: compatibility exports.
- `src/trace/tools/tgraph/model.py`: delegate or adapt to new core where safe.
- `src/trace/tools/tgraph/runtime.py`: reduce to compatibility wrapper over new core/query where safe.
- `src/trace/tools/tgraph/patch.py`: delegate graph patch operations to new patch engine while keeping TRACE artifact envelope support.
- `src/trace/tools/tgraph/export.py`: delegate TGraph JSON export to new IO and target placeholder.
- Existing tests under `tests/unit/tools/tgraph/`: keep passing during migration.

## Chunk 1: Package Boundary And Core IR

### Task 1: Add the new `tgraph` package shell

**Files:**
- Create: `src/tgraph/__init__.py`
- Create: `src/tgraph/core/__init__.py`
- Create: `src/tgraph/core/stage.py`
- Create: `src/tgraph/core/errors.py`
- Test: `tests/unit/tgraph/core/test_graph.py`

- [ ] **Step 1: Write failing package import tests**

Add:

```python
def test_tgraph_package_imports_public_api():
    import tgraph

    assert hasattr(tgraph, "TGraph")
    assert hasattr(tgraph, "GraphStage")
```

- [ ] **Step 2: Run the failing test**

Run: `python -m pytest tests/unit/tgraph/core/test_graph.py::test_tgraph_package_imports_public_api -q`

Expected: FAIL because `tgraph` does not exist.

- [ ] **Step 3: Create minimal package files**

Add `src/tgraph/core/stage.py`:

```python
from __future__ import annotations

from typing import Literal

GraphStage = Literal["logical", "physical"]


def ensure_stage(value: str) -> GraphStage:
    if value not in {"logical", "physical"}:
        raise ValueError(f"unsupported graph stage: {value}")
    return value  # type: ignore[return-value]
```

Add `src/tgraph/core/errors.py`:

```python
from __future__ import annotations


class TGraphError(Exception):
    code = "tgraph_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_json(self) -> dict:
        payload = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload
```

Add exports in `src/tgraph/core/__init__.py` and `src/tgraph/__init__.py`. Temporarily export `GraphStage` only until `TGraph` exists.

- [ ] **Step 4: Run package import test again**

Run: `python -m pytest tests/unit/tgraph/core/test_graph.py::test_tgraph_package_imports_public_api -q`

Expected: still FAIL on missing `TGraph`.

- [ ] **Step 5: Commit package shell if useful**

Do not commit yet if Task 2 follows immediately in the same working set.

### Task 2: Add the canonical TGraph core model

**Files:**
- Create: `src/tgraph/core/graph.py`
- Modify: `src/tgraph/core/__init__.py`
- Modify: `src/tgraph/__init__.py`
- Test: `tests/unit/tgraph/core/test_graph.py`

- [ ] **Step 1: Write failing canonical document tests**

Add tests:

```python
def test_minimal_tgraph_document_shape():
    from tgraph import TGraph

    graph = TGraph.model_validate({"stage": "logical", "nodes": [], "links": []})

    assert graph.stage == "logical"
    assert graph.nodes == []
    assert graph.links == []
    assert graph.model_dump(mode="json") == {
        "stage": "logical",
        "nodes": [],
        "links": [],
    }


def test_rejects_deferred_header_fields():
    from pydantic import ValidationError
    from tgraph import TGraph

    for field in ("schema_version", "profile", "metadata"):
        with pytest.raises(ValidationError):
            TGraph.model_validate({"stage": "logical", "nodes": [], "links": [], field: {}})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/tgraph/core/test_graph.py -q`

Expected: FAIL because `TGraph` and graph models are missing.

- [ ] **Step 3: Implement core graph models**

Implement `src/tgraph/core/graph.py`:

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from tgraph.core.stage import GraphStage


class ImageSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str


class FlavorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vcpu: int
    ram: int
    disk: int


class Port(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    ip: str = ""
    cidr: str = ""


class Node(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["switch", "router", "computer"]
    label: str
    ports: list[Port] = Field(default_factory=list)
    image: ImageSpec | None = None
    flavor: FlavorSpec | None = None


class Link(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    from_port: str
    to_port: str
    from_node: str | None = None
    to_node: str | None = None


class TGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: GraphStage
    nodes: list[Node] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
```

- [ ] **Step 4: Export public symbols**

Update `src/tgraph/core/__init__.py` and `src/tgraph/__init__.py` to export `TGraph`, `Node`, `Port`, `Link`, `ImageSpec`, `FlavorSpec`, and `GraphStage`.

- [ ] **Step 5: Run core graph tests**

Run: `python -m pytest tests/unit/tgraph/core/test_graph.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/tgraph tests/unit/tgraph/core/test_graph.py
git commit -m "feat: add standalone tgraph core model"
```

## Chunk 2: Normalization And IO

### Task 3: Add deterministic normalization

**Files:**
- Create: `src/tgraph/core/normalize.py`
- Modify: `src/tgraph/__init__.py`
- Test: `tests/unit/tgraph/core/test_normalize.py`

- [ ] **Step 1: Write failing normalization tests**

Cover:

- Link IDs are canonical as `sorted_port_a--sorted_port_b`.
- `from_port` and `to_port` are ordered consistently.
- `from_node` and `to_node` are inferred from port ownership.
- Nodes, ports, and links have stable ordering.
- Normalization is idempotent.

Example:

```python
def test_normalize_canonicalizes_link_ids_and_endpoint_order():
    from tgraph import TGraph, normalize_graph

    graph = TGraph.model_validate({
        "stage": "logical",
        "nodes": [
            {"id": "B", "type": "computer", "label": "B", "ports": [{"id": "b1"}]},
            {"id": "A", "type": "router", "label": "A", "ports": [{"id": "a1"}]},
        ],
        "links": [{"id": "wrong", "from_port": "b1", "to_port": "a1"}],
    })

    normalized = normalize_graph(graph)

    assert normalized.links[0].id == "a1--b1"
    assert normalized.links[0].from_port == "a1"
    assert normalized.links[0].to_port == "b1"
    assert normalized.links[0].from_node == "A"
    assert normalized.links[0].to_node == "B"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/tgraph/core/test_normalize.py -q`

Expected: FAIL because `normalize_graph` does not exist.

- [ ] **Step 3: Implement `normalize_graph`**

Use a copy, not in-place mutation. Avoid importing TRACE runtime.

Implementation outline:

```python
def normalize_graph(graph: TGraph | dict) -> TGraph:
    current = graph if isinstance(graph, TGraph) else TGraph.model_validate(graph)
    data = current.model_dump(mode="json")
    # sort nodes by id
    # sort each node's ports by id
    # build port_owner map
    # canonicalize each link id and endpoint order
    # sort links by id
    return TGraph.model_validate(data)
```

- [ ] **Step 4: Run normalization tests**

Run: `python -m pytest tests/unit/tgraph/core/test_normalize.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tgraph/core/normalize.py src/tgraph/__init__.py tests/unit/tgraph/core/test_normalize.py
git commit -m "feat: add tgraph normalization"
```

### Task 4: Add TGraph JSON IO

**Files:**
- Create: `src/tgraph/io/__init__.py`
- Create: `src/tgraph/io/json.py`
- Create: `src/tgraph/io/document.py`
- Modify: `src/tgraph/__init__.py`
- Test: `tests/unit/tgraph/io/test_json.py`

- [ ] **Step 1: Write failing IO tests**

Cover:

- `load_tgraph` accepts dict and JSON string/path.
- `dump_tgraph` returns stable dict or JSON string.
- Unknown top-level fields are rejected.
- Load normalizes by default.

Example:

```python
def test_load_tgraph_rejects_unknown_top_level_fields():
    from tgraph import load_tgraph
    from tgraph.core.errors import TGraphError

    with pytest.raises(TGraphError) as exc:
        load_tgraph({"stage": "logical", "nodes": [], "links": [], "metadata": {}})

    assert exc.value.code == "document_error"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/tgraph/io/test_json.py -q`

Expected: FAIL because IO modules do not exist.

- [ ] **Step 3: Implement IO helpers**

`document.py` should own allowed top-level fields:

```python
ALLOWED_TOP_LEVEL_FIELDS = {"stage", "nodes", "links"}
```

Reject unknown fields before Pydantic validation so the error code is stable.

`json.py` should provide:

```python
def load_tgraph(value: dict | str | Path, *, normalize: bool = True) -> TGraph: ...
def dump_tgraph(graph: TGraph, *, as_json: bool = False) -> dict | str: ...
```

- [ ] **Step 4: Export IO helpers**

Update `src/tgraph/io/__init__.py` and `src/tgraph/__init__.py`.

- [ ] **Step 5: Run IO tests**

Run: `python -m pytest tests/unit/tgraph/io/test_json.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/tgraph/io src/tgraph/__init__.py tests/unit/tgraph/io/test_json.py
git commit -m "feat: add tgraph json io"
```

## Chunk 3: Validation Runner

### Task 5: Add validation issue and policy models

**Files:**
- Create: `src/tgraph/operations/__init__.py`
- Create: `src/tgraph/operations/validate/__init__.py`
- Create: `src/tgraph/operations/validate/issues.py`
- Create: `src/tgraph/operations/validate/policy.py`
- Test: `tests/unit/tgraph/operations/test_validate.py`

- [ ] **Step 1: Write failing model tests**

Add tests for:

- `ValidationIssue` JSON shape.
- `ValidationReport.ok` derived from issue severities or explicitly set.
- `ValidationPolicy` defaults to `["f1", "f2", "f3", "f4"]`.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/tgraph/operations/test_validate.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement issue and policy models**

Use stable fields compatible with agent output:

```python
class ValidationIssue(BaseModel):
    code: str
    message: str
    severity: Literal["error", "warning"] = "error"
    location: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationReport(BaseModel):
    ok: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
```

`ValidationPolicy` should include:

```python
levels: list[Literal["f1", "f2", "f3", "f4"]]
stage: GraphStage | None
```

- [ ] **Step 4: Run model tests**

Run: `python -m pytest tests/unit/tgraph/operations/test_validate.py -q`

Expected: PASS for model tests.

### Task 6: Implement F1-F3 validation

**Files:**
- Create: `src/tgraph/operations/validate/f1_format.py`
- Create: `src/tgraph/operations/validate/f2_schema.py`
- Create: `src/tgraph/operations/validate/f3_graph.py`
- Create: `src/tgraph/operations/validate/runner.py`
- Modify: `src/tgraph/operations/validate/__init__.py`
- Modify: `src/tgraph/__init__.py`
- Test: `tests/unit/tgraph/operations/test_validate.py`

- [ ] **Step 1: Write failing validation behavior tests**

Cover:

- F1 rejects non-dict raw document.
- F1 rejects unknown top-level fields.
- F2 rejects invalid stage and invalid node type.
- F3 rejects links referencing unknown ports.
- F3 rejects duplicate node IDs.
- F3 rejects duplicate port IDs.
- F3 rejects non-canonical link IDs after normalization policy check.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/tgraph/operations/test_validate.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement validators**

Keep validators pure:

```python
def f1_format(raw: Any) -> list[ValidationIssue]: ...
def f2_schema(raw: dict) -> list[ValidationIssue]: ...
def f3_graph(graph: TGraph) -> list[ValidationIssue]: ...
```

Do not import TRACE validators. Port logic from `src/trace/tools/tgraph/validate/f3_consistency.py` only where it matches the new minimal IR.

- [ ] **Step 4: Implement runner**

Public functions:

```python
def validate_document(raw: Any, policy: ValidationPolicy | None = None) -> ValidationReport: ...
def validate_graph(graph: TGraph, policy: ValidationPolicy | None = None, context: ValidationContext | None = None) -> ValidationReport: ...
```

F1/F2 operate on raw document. F3 operates on parsed graph.

- [ ] **Step 5: Run validation tests**

Run: `python -m pytest tests/unit/tgraph/operations/test_validate.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/tgraph/operations/validate src/tgraph/__init__.py tests/unit/tgraph/operations/test_validate.py
git commit -m "feat: add standalone tgraph validation runner"
```

### Task 7: Add F4 caller context validation

**Files:**
- Create: `src/tgraph/operations/validate/f4_intent.py`
- Modify: `src/tgraph/operations/validate/policy.py`
- Modify: `src/tgraph/operations/validate/runner.py`
- Test: `tests/unit/tgraph/operations/test_validate.py`

- [ ] **Step 1: Write failing F4 tests**

Cover:

- `preserve_topology_from` detects missing node IDs.
- `preserve_topology_from` detects missing link endpoint pairs.
- `required_node_fields` detects missing `image` or `flavor` for physical validation when caller asks for it.
- Empty context produces no F4 issues.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/tgraph/operations/test_validate.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement `ValidationContext`**

In `policy.py`:

```python
class ValidationContext(BaseModel):
    preserve_topology_from: TGraph | None = None
    required_node_fields: list[str] = Field(default_factory=list)
    required_link_fields: list[str] = Field(default_factory=list)
    checkpoints: list[dict[str, Any]] = Field(default_factory=list)
```

- [ ] **Step 4: Implement minimal F4 checks**

Do not implement catalog/image knowledge. Only validate explicit context supplied by caller.

- [ ] **Step 5: Run validation tests**

Run: `python -m pytest tests/unit/tgraph/operations/test_validate.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/tgraph/operations/validate tests/unit/tgraph/operations/test_validate.py
git commit -m "feat: add context-aware tgraph validation"
```

## Chunk 4: Inspection Operations

### Task 8: Add graph inspection views

**Files:**
- Create: `src/tgraph/operations/inspect/__init__.py`
- Create: `src/tgraph/operations/inspect/summary.py`
- Create: `src/tgraph/operations/inspect/nodes.py`
- Create: `src/tgraph/operations/inspect/ports.py`
- Create: `src/tgraph/operations/inspect/links.py`
- Create: `src/tgraph/operations/inspect/paths.py`
- Create: `src/tgraph/operations/inspect/segments.py`
- Modify: `src/tgraph/__init__.py`
- Test: `tests/unit/tgraph/operations/test_inspect.py`

- [ ] **Step 1: Write failing inspect tests**

Cover:

- Summary returns node/link counts by type.
- Node lookup returns one node or `None`.
- Link lookup returns links by node or port.
- Path query returns reachable path between nodes.
- Segment view groups switch CIDRs when available.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/tgraph/operations/test_inspect.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement inspect functions**

Keep return values JSON-serializable dictionaries, not Pydantic unless useful.

Public facade:

```python
def inspect_graph(graph: TGraph, *, view: str = "summary", **kwargs: Any) -> dict: ...
```

- [ ] **Step 4: Run inspect tests**

Run: `python -m pytest tests/unit/tgraph/operations/test_inspect.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tgraph/operations/inspect src/tgraph/__init__.py tests/unit/tgraph/operations/test_inspect.py
git commit -m "feat: add tgraph inspection operations"
```

## Chunk 5: Batch Patch Engine

### Task 9: Add patch schemas and result models

**Files:**
- Create: `src/tgraph/operations/patch/__init__.py`
- Create: `src/tgraph/operations/patch/schema.py`
- Create: `src/tgraph/operations/patch/result.py`
- Create: `src/tgraph/operations/patch/diff.py`
- Create: `src/tgraph/operations/patch/errors.py`
- Test: `tests/unit/tgraph/operations/test_patch.py`

- [ ] **Step 1: Write failing schema tests**

Cover:

- Patch accepts `graph_patch` list.
- Unknown operations fail with `patch_schema_error`.
- Result has `ok`, `would_commit`, `accepted_ops`, `rejected_ops`, `diff`, `validation`, and `error`.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/tgraph/operations/test_patch.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement patch models**

Start with graph-only patch operations:

- `ensure_node`
- `ensure_port`
- `ensure_link`
- `remove_node`
- `remove_port`
- `remove_link`
- `set_stage`

Do not include checkpoint or validator script patching in the standalone core. TRACE can keep envelope-level checkpoint patching in its adapter.

- [ ] **Step 4: Run schema tests**

Run: `python -m pytest tests/unit/tgraph/operations/test_patch.py -q`

Expected: PASS for schema tests.

### Task 10: Implement atomic graph patch application

**Files:**
- Create: `src/tgraph/operations/patch/apply.py`
- Modify: `src/tgraph/operations/patch/__init__.py`
- Modify: `src/tgraph/__init__.py`
- Test: `tests/unit/tgraph/operations/test_patch.py`

- [ ] **Step 1: Write failing patch behavior tests**

Cover:

- `ensure_node` creates and merges.
- `ensure_port` creates a port under a node.
- `ensure_link` creates missing endpoint ports only when node is specified.
- `ensure_link` rejects connected ports unless `reconnect=true`.
- `remove_node` respects `cascade`.
- `remove_port` rejects incident links unless `cascade=true`.
- `set_stage` changes graph stage.
- Failed operation leaves original graph unchanged.
- `validate=true` runs validation and blocks invalid candidate.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/tgraph/operations/test_patch.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement patch application**

Use `copy.deepcopy` or Pydantic dumps to create a candidate. Normalize after operation application. Call `validate_graph` when requested.

Public function:

```python
def apply_patch(
    graph: TGraph | dict,
    patch: TGraphPatch | dict,
    *,
    validate: bool = True,
    include_graph: bool = False,
) -> PatchResult:
    ...
```

- [ ] **Step 4: Run patch tests**

Run: `python -m pytest tests/unit/tgraph/operations/test_patch.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tgraph/operations/patch src/tgraph/__init__.py tests/unit/tgraph/operations/test_patch.py
git commit -m "feat: add standalone tgraph patch engine"
```

## Chunk 6: Targets And CLI

### Task 11: Add target emitter placeholders

**Files:**
- Create: `src/tgraph/targets/__init__.py`
- Create: `src/tgraph/targets/base.py`
- Create: `src/tgraph/targets/result.py`
- Create: `src/tgraph/targets/registry.py`
- Create: `src/tgraph/targets/terraform.py`
- Create: `src/tgraph/targets/pulumi.py`
- Create: `src/tgraph/targets/tosca.py`
- Modify: `src/tgraph/__init__.py`
- Test: `tests/unit/tgraph/targets/test_registry.py`

- [ ] **Step 1: Write failing target tests**

Cover:

- Registry lists `terraform`, `pulumi`, and `tosca`.
- Placeholder emitters return `ok=false`.
- Error code is `target_not_implemented`.
- `tgraph-json` is not listed as a target.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/tgraph/targets/test_registry.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement target models and registry**

Keep output bundle generic:

```python
class EmitResult(BaseModel):
    ok: bool
    target: str
    files: list[GeneratedFile] = Field(default_factory=list)
    error: dict[str, Any] | None = None
```

- [ ] **Step 4: Run target tests**

Run: `python -m pytest tests/unit/tgraph/targets/test_registry.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tgraph/targets src/tgraph/__init__.py tests/unit/tgraph/targets/test_registry.py
git commit -m "feat: add tgraph target emitter placeholders"
```

### Task 12: Add CLI wrapper

**Files:**
- Create: `src/tgraph/cli/__init__.py`
- Create: `src/tgraph/cli/main.py`
- Modify: `pyproject.toml`
- Test: `tests/unit/tgraph/cli/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Use `typer.testing.CliRunner`.

Cover:

- `tgraph validate graph.json --json`
- `tgraph inspect graph.json --view summary --json`
- `tgraph patch graph.json patch.json --json`
- `tgraph normalize graph.json --out normalized.json`
- `tgraph export json graph.json --out graph.json`
- `tgraph emit terraform graph.json --json` returns `target_not_implemented`

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/tgraph/cli/test_cli.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement Typer app**

Use existing project style from `src/trace_cli.py` where useful, but do not import TRACE.

All `--json` responses should print stable JSON.

- [ ] **Step 4: Add console script**

Update `pyproject.toml`:

```toml
[project.scripts]
trace = "trace_cli:app"
tgraph = "tgraph.cli.main:app"
```

- [ ] **Step 5: Run CLI tests**

Run: `python -m pytest tests/unit/tgraph/cli/test_cli.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/tgraph/cli pyproject.toml tests/unit/tgraph/cli/test_cli.py
git commit -m "feat: add tgraph cli"
```

## Chunk 7: Agent Protocol Documents

### Task 13: Add agent schemas and playbooks

**Files:**
- Create: `src/tgraph/agent/__init__.py`
- Create: `src/tgraph/agent/protocol.py`
- Create: `src/tgraph/agent/schemas/tgraph.schema.json`
- Create: `src/tgraph/agent/schemas/patch.schema.json`
- Create: `src/tgraph/agent/schemas/validation-report.schema.json`
- Create: `src/tgraph/agent/schemas/inspect-result.schema.json`
- Create: `src/tgraph/agent/playbooks/repair.md`
- Create: `src/tgraph/agent/playbooks/authoring.md`
- Create: `src/tgraph/agent/playbooks/validation.md`
- Create: `src/tgraph/agent/playbooks/emission.md`
- Test: `tests/unit/tgraph/agent/test_schemas.py`

- [ ] **Step 1: Write failing schema tests**

Cover:

- Schema files exist.
- Example minimal graph validates against `tgraph.schema.json`.
- Example patch validates against `patch.schema.json`.
- Playbooks mention inspect, patch, validate, and no knowledge/catalog ownership.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/tgraph/agent/test_schemas.py -q`

Expected: FAIL.

- [ ] **Step 3: Add schemas**

If generating schemas from Pydantic is straightforward, generate and commit stable JSON. If not, hand-maintain minimal phase-one schemas and keep tests aligned.

- [ ] **Step 4: Add playbooks**

Keep playbooks short and operational:

```text
inspect -> patch -> validate -> repeat -> emit
```

Explicitly state that agents must not invent image catalog, domain knowledge, or workflow decisions inside TGraph.

- [ ] **Step 5: Run schema tests**

Run: `python -m pytest tests/unit/tgraph/agent/test_schemas.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/tgraph/agent tests/unit/tgraph/agent/test_schemas.py
git commit -m "docs: add tgraph agent protocol"
```

## Chunk 8: TRACE Compatibility Adapters

### Task 14: Keep existing TRACE TGraph imports working

**Files:**
- Modify: `src/trace/tools/tgraph/__init__.py`
- Modify: `src/trace/tools/tgraph/model.py`
- Test: `tests/unit/tools/tgraph/test_model.py`
- Test: `tests/unit/config/test_packaging.py`

- [ ] **Step 1: Write compatibility tests**

Add or update tests to assert:

- `from trace.tools.tgraph import TGraphJSON` still works.
- `from tgraph import TGraph` works.
- Existing TRACE artifacts with `profile` still validate through the TRACE compatibility model.
- New canonical TGraph documents do not require `profile`.

- [ ] **Step 2: Run targeted tests**

Run: `python -m pytest tests/unit/tools/tgraph/test_model.py tests/unit/config/test_packaging.py -q`

Expected: existing tests PASS or new compatibility tests FAIL before adapter update.

- [ ] **Step 3: Add adapters carefully**

Do not delete `TGraphJSON` yet. It can remain a TRACE compatibility model for old artifacts. Add conversion helpers:

```python
def to_standalone_graph(graph: TGraphJSON | dict) -> tgraph.TGraph: ...
def from_standalone_graph(graph: tgraph.TGraph, *, profile: str = TAAL_DEFAULT_V1) -> TGraphJSON: ...
```

This avoids a flag-day migration of current TRACE artifacts.

- [ ] **Step 4: Run compatibility tests**

Run: `python -m pytest tests/unit/tools/tgraph/test_model.py tests/unit/config/test_packaging.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/trace/tools/tgraph src/tgraph tests/unit/tools/tgraph/test_model.py tests/unit/config/test_packaging.py
git commit -m "refactor: bridge trace tgraph models to standalone package"
```

### Task 15: Delegate TRACE graph operations to standalone package

**Files:**
- Modify: `src/trace/tools/tgraph/runtime.py`
- Modify: `src/trace/tools/tgraph/patch.py`
- Modify: `src/trace/tools/tgraph/export.py`
- Test: `tests/unit/tools/tgraph/test_graph_core.py`
- Test: `tests/unit/tools/tgraph/test_patch_protocol.py`
- Test: `tests/unit/tools/tgraph/test_export.py`

- [ ] **Step 1: Run current TRACE tests as baseline**

Run:

```bash
python -m pytest tests/unit/tools/tgraph/test_graph_core.py tests/unit/tools/tgraph/test_patch_protocol.py tests/unit/tools/tgraph/test_export.py -q
```

Expected: PASS before changes.

- [ ] **Step 2: Refactor one adapter at a time**

Start with export because it should be smallest. Delegate `tgraph-json` output to `tgraph.io`.

- [ ] **Step 3: Run export tests**

Run: `python -m pytest tests/unit/tools/tgraph/test_export.py -q`

Expected: PASS.

- [ ] **Step 4: Refactor patch graph operations**

Keep TRACE artifact envelope logic in `src/trace/tools/tgraph/patch.py`, but delegate graph-only patch application to `tgraph.operations.patch` where possible.

Do not move checkpoint patching into standalone TGraph.

- [ ] **Step 5: Run patch tests**

Run: `python -m pytest tests/unit/tools/tgraph/test_patch_protocol.py -q`

Expected: PASS.

- [ ] **Step 6: Refactor runtime normalization/query carefully**

`TGraphRuntime` may remain a compatibility wrapper. Replace internal normalization with `tgraph.normalize_graph` only if all existing behavior is preserved.

- [ ] **Step 7: Run graph core tests**

Run: `python -m pytest tests/unit/tools/tgraph/test_graph_core.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/trace/tools/tgraph tests/unit/tools/tgraph
git commit -m "refactor: delegate trace tgraph operations to standalone engine"
```

## Chunk 9: Full Verification And Cleanup

### Task 16: Run full verification

**Files:**
- No planned source edits.

- [ ] **Step 1: Run standalone package tests**

Run: `python -m pytest tests/unit/tgraph -q`

Expected: PASS.

- [ ] **Step 2: Run existing TGraph tests**

Run: `python -m pytest tests/unit/tools/tgraph -q`

Expected: PASS.

- [ ] **Step 3: Run skill tests**

Run: `python -m pytest tests/unit/skills -q`

Expected: PASS.

- [ ] **Step 4: Run all tests**

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 5: Inspect git status**

Run: `git status --short --branch`

Expected: clean working tree after final commit.

### Task 17: Update documentation references if needed

**Files:**
- Modify only if implementation changed documented commands:
  - `skills/tgraph-iac/references/patch-protocol.md`
  - `skills/tgraph-iac/references/tgraph-ir.md`
  - `skills/tgraph-iac/references/validation.md`
  - `README.md`

- [ ] **Step 1: Search old namespace references**

Run: `rg "trace_tgraph|trace\\.tools\\.tgraph|profile|schema_version|metadata" docs skills README.md src/tgraph`

Expected: only intentional compatibility references remain.

- [ ] **Step 2: Update docs only where user-facing behavior changed**

Do not rewrite unrelated docs.

- [ ] **Step 3: Run docs-related tests**

Run: `python -m pytest tests/unit/config/test_prompts.py tests/unit/skills -q`

Expected: PASS.

- [ ] **Step 4: Commit docs cleanup**

Only commit if docs changed:

```bash
git add README.md skills/tgraph-iac docs
git commit -m "docs: align tgraph standalone package references"
```

## Final Acceptance Criteria

- `import tgraph` works without importing TRACE.
- New canonical TGraph documents require only `stage`, `nodes`, and `links`.
- `schema_version`, `profile`, and top-level `metadata` are rejected by new standalone document IO.
- Existing TRACE tests still pass through compatibility adapters.
- Public standalone mutation is batch patch only.
- Validation supports F1-F4 with caller-supplied context for F4.
- CLI supports inspect, validate, patch, normalize, import/export JSON, and placeholder emit.
- `tgraph emit terraform` returns a stable `target_not_implemented` result.
- Agent schemas and playbooks exist and do not claim ownership of knowledge/catalog/workflow.
- `python -m pytest -q` passes.

