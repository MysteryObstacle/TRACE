# TRACE TGraph Core Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the TGraph domain core so `logical` and `physical` share a profile-aware graph model with stable JSON import/export, F1-F3 validation, patch/query/materialize operations, and thin runtime integration.

**Architecture:** Build a canonical TGraph model under `tools/tgraph` with two explicit JSON profiles, `logical.v1` and `taal.default.v1`, then route runtime validation and patch application through thin adapters in `validators/`. Deliver the work in four chunks so the repository can move from the current placeholder `nodes/edges` shape to `nodes/links` without breaking the runner mid-migration.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, standard library `ipaddress`, existing TRACE runtime modules

---

**Execution notes:** Use `@test-driven-development` for every task, `@verification-before-completion` before claiming the rollout is done, and `@receiving-code-review` if follow-up review feedback arrives.

## File Map

### Files to create

- `tools/tgraph/model/link.py`
- `tools/tgraph/model/port.py`
- `tools/tgraph/model/profiles.py`
- `tools/tgraph/model/indexes.py`
- `tools/tgraph/io/__init__.py`
- `tools/tgraph/io/load.py`
- `tools/tgraph/io/json_loader.py`
- `tools/tgraph/io/gml_loader.py`
- `tools/tgraph/io/gns3_loader.py`
- `tools/tgraph/query/__init__.py`
- `tools/tgraph/query/graph.py`
- `tools/tgraph/query/node.py`
- `tools/tgraph/query/port.py`
- `tools/tgraph/query/path.py`
- `tools/tgraph/query/segment.py`
- `tools/tgraph/validate/issues.py`
- `tools/tgraph/validate/runner.py`
- `tools/tgraph/docs/export.md`
- `tools/tgraph/docs/profiles.md`
- `tools/tgraph/docs/init.md`
- `tools/tgraph/docs/validation.md`
- `tools/tgraph/docs/materialize.md`
- `tools/tgraph/docs/patch.md`
- `tools/tgraph/docs/query.md`
- `tests/unit/test_tgraph_models.py`
- `tests/unit/test_tgraph_serialize.py`
- `tests/unit/test_tgraph_import.py`
- `tests/unit/test_tgraph_validate_schema.py`
- `tests/unit/test_tgraph_validate_consistency.py`
- `tests/unit/test_tgraph_query.py`
- `tests/unit/test_tgraph_materialize.py`

### Files to modify

- `app/contracts.py`
- `app/container.py`
- `stages/logical/guard.py`
- `stages/physical/guard.py`
- `validators/tgraph_runner.py`
- `validators/patching.py`
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
- `tests/unit/test_checkpoint_runner.py`
- `tests/unit/test_patch_ops.py`
- `tests/unit/test_stage_runtime.py`
- `tests/unit/test_tplan_runner.py`
- `tests/integration/test_ground_to_logical.py`
- `tests/integration/test_logical_to_physical.py`

### Responsibility notes

- `tools/tgraph/model/*` owns canonical graph data and indexes.
- `tools/tgraph/io/*` owns loading external payloads into the canonical graph.
- `tools/tgraph/ops/*` owns export, materialization, and patch logic.
- `tools/tgraph/query/*` owns reusable graph algorithms and read-only queries.
- `tools/tgraph/validate/*` owns F1-F4 validation and issue construction.
- `validators/*` stays thin and delegates to `tools/tgraph/*`.
- `edge.py` should remain as a temporary compatibility shim that re-exports `Link` while the repo migrates to `links` terminology.

## Implementation order

1. Lock the canonical graph contract, profile names, issue scopes, and JSON export.
2. Add import entrypoints plus profile-aware F1-F3 validation and move the runtime adapter onto them.
3. Add reusable query, materialize, and patch behavior on top of the canonical graph.
4. Migrate fake fixtures, stage guards, and docs so the runtime and prompts use the new TGraph contract consistently.

## Chunk 1: Canonical Model, Profiles, and JSON Export

### Task 1: Expand shared validation contracts for TGraph issue scopes

**Files:**
- Modify: `app/contracts.py`
- Modify: `tests/unit/test_contracts.py`
- Test: `tests/unit/test_contracts.py`

- [ ] **Step 1: Write the failing contract tests**

```python
from app.contracts import ValidationIssue


def test_validation_issue_accepts_tgraph_scopes() -> None:
    issue = ValidationIssue(
        code="duplicate_port_id",
        message="port id duplicated",
        severity="error",
        scope="port",
    )
    assert issue.scope == "port"
    assert issue.targets == []
    assert issue.json_paths == []
```

- [ ] **Step 2: Run the contract test to verify it fails**

Run: `pytest tests/unit/test_contracts.py -v`
Expected: FAIL with a Pydantic validation error because `scope="port"` is not accepted yet.

- [ ] **Step 3: Widen the issue scope literal for TGraph work**

```python
class ValidationIssue(BaseModel):
    code: str
    message: str
    severity: Literal["error", "warning"]
    scope: Literal["topology", "node", "port", "link", "patch", "intent"]
    targets: list[str] = Field(default_factory=list)
    json_paths: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run the contract test again**

Run: `pytest tests/unit/test_contracts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/contracts.py tests/unit/test_contracts.py
git commit -m "feat: widen tgraph validation issue scopes"
```

### Task 2: Build canonical TGraph models and profile constants

**Files:**
- Create: `tools/tgraph/model/link.py`
- Create: `tools/tgraph/model/port.py`
- Create: `tools/tgraph/model/profiles.py`
- Create: `tools/tgraph/model/indexes.py`
- Modify: `tools/tgraph/model/tgraph.py`
- Modify: `tools/tgraph/model/node.py`
- Modify: `tools/tgraph/model/edge.py`
- Modify: `tools/tgraph/model/__init__.py`
- Modify: `tools/tgraph/__init__.py`
- Test: `tests/unit/test_tgraph_models.py`

- [ ] **Step 1: Write the failing model tests**

```python
from tools.tgraph.model.link import Link
from tools.tgraph.model.node import Node
from tools.tgraph.model.port import Port
from tools.tgraph.model.tgraph import TGraph


def test_tgraph_builds_indexes_for_nodes_ports_and_links() -> None:
    graph = TGraph(
        profile="logical.v1",
        nodes=[
            Node(
                id="R1",
                type="router",
                label="R1",
                ports=[Port(id="R1:p1", ip="10.0.0.1", cidr="10.0.0.0/24")],
                image=None,
                flavor=None,
            )
        ],
        links=[
            Link(
                id="R1:p1--PC1:p1",
                from_port="R1:p1",
                to_port="PC1:p1",
                from_node="R1",
                to_node="PC1",
            )
        ],
    )

    indexes = graph.build_indexes()
    assert indexes.port_owner["R1:p1"] == "R1"
    assert indexes.link_by_id["R1:p1--PC1:p1"].from_node == "R1"
```

- [ ] **Step 2: Run the model tests to verify they fail**

Run: `pytest tests/unit/test_tgraph_models.py -v`
Expected: FAIL with import errors because the new models and index helpers do not exist yet.

- [ ] **Step 3: Implement the canonical models and compatibility shim**

```python
class Port(BaseModel):
    id: str
    ip: str = ""
    cidr: str = ""


class Link(BaseModel):
    id: str
    from_port: str
    to_port: str
    from_node: str | None = None
    to_node: str | None = None


class TGraph(BaseModel):
    profile: str
    nodes: list[Node] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)

    def build_indexes(self) -> TGraphIndexes:
        return build_indexes(self)
```

- [ ] **Step 4: Keep `edge.py` as a compatibility alias while migrating callers**

```python
from tools.tgraph.model.link import Link

Edge = Link
```

- [ ] **Step 5: Run the model tests again**

Run: `pytest tests/unit/test_tgraph_models.py tests/unit/test_contracts.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tools/tgraph/model tools/tgraph/__init__.py tests/unit/test_tgraph_models.py
git commit -m "feat: add canonical tgraph models"
```

### Task 3: Add stable JSON serialization and export for TGraph profiles

**Files:**
- Modify: `tools/tgraph/ops/serialize.py`
- Modify: `tools/tgraph/ops/__init__.py`
- Create: `tests/unit/test_tgraph_serialize.py`
- Test: `tests/unit/test_tgraph_serialize.py`

- [ ] **Step 1: Write the failing export tests**

```python
import json

from tools.tgraph.ops.serialize import export_tgraph_json, serialize


def test_serialize_logical_profile_emits_links_and_profile() -> None:
    graph = {"profile": "logical.v1", "nodes": [], "links": []}
    payload = serialize(graph, profile="logical.v1")
    assert payload["profile"] == "logical.v1"
    assert "links" in payload
    assert "edges" not in payload


def test_export_tgraph_json_returns_valid_json_text() -> None:
    graph = {"profile": "logical.v1", "nodes": [], "links": []}
    text = export_tgraph_json(graph, profile="logical.v1")
    payload = json.loads(text)
    assert payload["profile"] == "logical.v1"
```

- [ ] **Step 2: Run the serialization tests to verify they fail**

Run: `pytest tests/unit/test_tgraph_serialize.py -v`
Expected: FAIL because `serialize()` does not accept a profile and `export_tgraph_json()` does not exist yet.

- [ ] **Step 3: Implement deterministic serialization**

```python
def serialize(graph: TGraph | dict, profile: str) -> dict[str, Any]:
    model = ensure_tgraph(graph)
    if model.profile != profile:
        raise ValueError(f"export_profile_mismatch:{model.profile}->{profile}")
    return model.model_dump(mode="json")


def export_tgraph_json(graph: TGraph | dict, profile: str) -> str:
    payload = serialize(graph, profile=profile)
    return json.dumps(payload, sort_keys=True)
```

- [ ] **Step 4: Run the serialization tests again**

Run: `pytest tests/unit/test_tgraph_serialize.py tests/unit/test_tgraph_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/tgraph/ops/serialize.py tools/tgraph/ops/__init__.py tests/unit/test_tgraph_serialize.py
git commit -m "feat: add stable tgraph json export"
```

## Chunk 2: Import and F1-F3 Validation Core

### Task 4: Add JSON import plus explicit stub loaders for `.gml` and `.gns3`

**Files:**
- Create: `tools/tgraph/io/__init__.py`
- Create: `tools/tgraph/io/load.py`
- Create: `tools/tgraph/io/json_loader.py`
- Create: `tools/tgraph/io/gml_loader.py`
- Create: `tools/tgraph/io/gns3_loader.py`
- Create: `tests/unit/test_tgraph_import.py`
- Test: `tests/unit/test_tgraph_import.py`

- [ ] **Step 1: Write the failing import tests**

```python
from pathlib import Path

from tools.tgraph.io.load import load_tgraph


def test_load_tgraph_auto_reads_json_profile(tmp_path: Path) -> None:
    source = tmp_path / "logical.json"
    source.write_text('{"profile": "logical.v1", "nodes": [], "links": []}', encoding="utf-8")

    graph = load_tgraph(source)
    assert graph.profile == "logical.v1"


def test_load_tgraph_gml_stub_is_explicit() -> None:
    try:
        load_tgraph("topology.gml")
    except NotImplementedError as exc:
        assert "import_not_implemented" in str(exc)
    else:
        raise AssertionError("expected a stub loader failure")
```

- [ ] **Step 2: Run the import tests to verify they fail**

Run: `pytest tests/unit/test_tgraph_import.py -v`
Expected: FAIL because the loader package does not exist yet.

- [ ] **Step 3: Implement the import entrypoints**

```python
def load_tgraph(source: str | Path, format: str = "auto", target_profile: str = "logical.v1") -> TGraph:
    resolved = detect_format(source, format=format)
    if resolved == "json":
        return load_tgraph_json(source)
    if resolved == "gml":
        return load_tgraph_gml(source, target_profile=target_profile)
    if resolved == "gns3":
        return load_tgraph_gns3(source, target_profile=target_profile)
    raise ValueError(f"unsupported_import_format:{resolved}")
```

- [ ] **Step 4: Keep non-JSON loaders as stable stubs for now**

```python
def load_tgraph_gml(source: str | Path, target_profile: str = "logical.v1") -> TGraph:
    raise NotImplementedError("import_not_implemented:gml")
```

- [ ] **Step 5: Run the import tests again**

Run: `pytest tests/unit/test_tgraph_import.py tests/unit/test_tgraph_models.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tools/tgraph/io tests/unit/test_tgraph_import.py
git commit -m "feat: add tgraph import entrypoints"
```

### Task 5: Implement F1 and F2 profile-aware validation

**Files:**
- Create: `tools/tgraph/validate/issues.py`
- Create: `tools/tgraph/validate/runner.py`
- Modify: `tools/tgraph/validate/f1_format.py`
- Modify: `tools/tgraph/validate/f2_schema.py`
- Modify: `tools/tgraph/validate/__init__.py`
- Create: `tests/unit/test_tgraph_validate_schema.py`
- Test: `tests/unit/test_tgraph_validate_schema.py`

- [ ] **Step 1: Write the failing format and schema tests**

```python
from tools.tgraph.validate.f1_format import f1_format
from tools.tgraph.validate.f2_schema import f2_schema


def test_f1_format_requires_profile_nodes_and_links() -> None:
    issues = f1_format({"nodes": []})
    assert issues[0]["code"] == "missing_top_level_field"


def test_f2_schema_allows_null_image_and_flavor_in_logical_profile() -> None:
    issues = f2_schema(
        {
            "profile": "logical.v1",
            "nodes": [
                {
                    "id": "PC1",
                    "type": "computer",
                    "label": "PC1",
                    "ports": [],
                    "image": None,
                    "flavor": None,
                }
            ],
            "links": [],
        }
    )
    assert issues == []


def test_f2_schema_requires_computer_image_and_flavor_in_taal_profile() -> None:
    issues = f2_schema(
        {
            "profile": "taal.default.v1",
            "nodes": [
                {
                    "id": "PC1",
                    "type": "computer",
                    "label": "PC1",
                    "ports": [],
                    "image": None,
                    "flavor": None,
                }
            ],
            "links": [],
        }
    )
    assert {issue["code"] for issue in issues} >= {"computer_image_required", "computer_flavor_required"}
```

- [ ] **Step 2: Run the validation tests to verify they fail**

Run: `pytest tests/unit/test_tgraph_validate_schema.py -v`
Expected: FAIL because F1 and F2 are still stubs.

- [ ] **Step 3: Implement issue helpers and profile-aware checks**

```python
def issue(code: str, message: str, scope: str, *, targets: list[str] | None = None, json_paths: list[str] | None = None) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "severity": "error",
        "scope": scope,
        "targets": targets or [],
        "json_paths": json_paths or [],
    }
```

- [ ] **Step 4: Add a validation runner that can compose F1 and F2**

```python
def validate_tgraph_payload(tgraph: dict[str, Any]) -> list[dict[str, Any]]:
    issues = []
    issues.extend(f1_format(tgraph))
    if issues:
        return issues
    issues.extend(f2_schema(tgraph))
    return issues
```

- [ ] **Step 5: Run the schema tests again**

Run: `pytest tests/unit/test_tgraph_validate_schema.py tests/unit/test_contracts.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tools/tgraph/validate tests/unit/test_tgraph_validate_schema.py
git commit -m "feat: add tgraph format and schema validation"
```

### Task 6: Implement F3 consistency validation for ports, links, IPs, and per-type rules

**Files:**
- Modify: `tools/tgraph/validate/f3_consistency.py`
- Create: `tests/unit/test_tgraph_validate_consistency.py`
- Test: `tests/unit/test_tgraph_validate_consistency.py`

- [ ] **Step 1: Write the failing consistency tests**

```python
from tools.tgraph.validate.f3_consistency import f3_consistency


def test_f3_reports_duplicate_port_ids() -> None:
    issues = f3_consistency(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "R1", "type": "router", "label": "R1", "ports": [{"id": "p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
                {"id": "R2", "type": "router", "label": "R2", "ports": [{"id": "p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            ],
            "links": [],
        }
    )
    assert issues[0]["code"] == "duplicate_port_id"


def test_f3_reports_link_id_mismatch() -> None:
    issues = f3_consistency(
        {
            "profile": "logical.v1",
            "nodes": [],
            "links": [{"id": "wrong", "from_port": "A:p1", "to_port": "B:p1", "from_node": "A", "to_node": "B"}],
        }
    )
    assert issues[0]["code"] == "link_id_mismatch"
```

- [ ] **Step 2: Run the consistency tests to verify they fail**

Run: `pytest tests/unit/test_tgraph_validate_consistency.py -v`
Expected: FAIL because F3 still returns an empty list.

- [ ] **Step 3: Implement consistency rules with `ipaddress` and index lookups**

```python
network = ipaddress.ip_network(port.cidr, strict=False)
address = ipaddress.ip_address(port.ip)
if address not in network:
    issues.append(issue("ip_not_in_cidr", "ip must belong to cidr", "port", ...))
```

- [ ] **Step 4: Cover per-type rules for switch, router, and computer nodes**

```python
if node.type == "switch" and port.ip:
    issues.append(issue("switch_port_ip_forbidden", "switch ports must not carry host IPs", "port", ...))
```

- [ ] **Step 5: Run the consistency tests again**

Run: `pytest tests/unit/test_tgraph_validate_consistency.py tests/unit/test_tgraph_validate_schema.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tools/tgraph/validate/f3_consistency.py tests/unit/test_tgraph_validate_consistency.py
git commit -m "feat: add tgraph consistency validation"
```

### Task 7: Align the runtime validator bridge with `nodes/links` and builtin TGraph checks

**Files:**
- Modify: `validators/tgraph_runner.py`
- Modify: `tests/unit/test_checkpoint_runner.py`
- Test: `tests/unit/test_checkpoint_runner.py`

- [ ] **Step 1: Rewrite the checkpoint runner tests around the new shape**

```python
def test_checkpoint_runner_executes_builtin_function() -> None:
    report = run_checkpoints(
        tgraph={"profile": "logical.v1", "nodes": [], "links": []},
        checkpoints=[
            {
                "id": "c1",
                "function_name": "f1_format",
                "input_params": {},
                "description": "format check",
                "script_ref": None,
            }
        ],
        artifact_root=temp_dir,
    )
    assert report.ok is True
```

- [ ] **Step 2: Run the checkpoint tests to verify they fail**

Run: `pytest tests/unit/test_checkpoint_runner.py -v`
Expected: FAIL because the builtin format validator still expects `edges`.

- [ ] **Step 3: Make `validators/tgraph_runner.py` a thin adapter**

```python
from tools.tgraph.validate.f1_format import f1_format
from tools.tgraph.validate.f2_schema import f2_schema
from tools.tgraph.validate.f3_consistency import f3_consistency
from tools.tgraph.validate.f4_intent import f4_intent

BUILTIN_VALIDATORS = {
    "f1_format": f1_format,
    "f2_schema": f2_schema,
    "f3_consistency": f3_consistency,
    "f4_intent": f4_intent,
}
```

- [ ] **Step 4: Preserve generated-script execution without changing the runtime interface**

```python
def run_tgraph_checks(tgraph: dict[str, Any], checkpoints: list[dict[str, Any]], artifact_root: str | Path) -> ValidationReport:
    ...
```

- [ ] **Step 5: Run the checkpoint tests again**

Run: `pytest tests/unit/test_checkpoint_runner.py tests/unit/test_tgraph_validate_schema.py tests/unit/test_tgraph_validate_consistency.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add validators/tgraph_runner.py tests/unit/test_checkpoint_runner.py
git commit -m "refactor: route runtime checks through tgraph validators"
```

## Chunk 3: Query, Materialize, and Patch Operations

### Task 8: Add reusable query helpers and graph algorithms

**Files:**
- Create: `tools/tgraph/query/__init__.py`
- Create: `tools/tgraph/query/graph.py`
- Create: `tools/tgraph/query/node.py`
- Create: `tools/tgraph/query/port.py`
- Create: `tools/tgraph/query/path.py`
- Create: `tools/tgraph/query/segment.py`
- Create: `tests/unit/test_tgraph_query.py`
- Test: `tests/unit/test_tgraph_query.py`

- [ ] **Step 1: Write the failing query tests**

```python
from tools.tgraph.query.graph import connected_components
from tools.tgraph.query.port import owner_of


def test_owner_of_returns_the_port_owner() -> None:
    graph = {
        "profile": "taal.default.v1",
        "nodes": [
            {"id": "R1", "type": "router", "label": "R1", "ports": [{"id": "R1:p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            {"id": "PC1", "type": "computer", "label": "PC1", "ports": [{"id": "PC1:p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": {"id": "img", "name": "img"}, "flavor": {"vcpu": 1, "ram": 512, "disk": 10}},
            {"id": "R2", "type": "router", "label": "R2", "ports": [], "image": None, "flavor": None},
        ],
        "links": [{"id": "R1:p1--PC1:p1", "from_port": "R1:p1", "to_port": "PC1:p1", "from_node": "R1", "to_node": "PC1"}],
    }
    assert owner_of(graph, "R1:p1") == "R1"


def test_connected_components_groups_nodes_by_links() -> None:
    graph = {
        "profile": "taal.default.v1",
        "nodes": [
            {"id": "R1", "type": "router", "label": "R1", "ports": [{"id": "R1:p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            {"id": "PC1", "type": "computer", "label": "PC1", "ports": [{"id": "PC1:p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": {"id": "img", "name": "img"}, "flavor": {"vcpu": 1, "ram": 512, "disk": 10}},
            {"id": "R2", "type": "router", "label": "R2", "ports": [], "image": None, "flavor": None},
        ],
        "links": [{"id": "R1:p1--PC1:p1", "from_port": "R1:p1", "to_port": "PC1:p1", "from_node": "R1", "to_node": "PC1"}],
    }
    groups = connected_components(graph)
    assert groups == [{"PC1", "R1"}, {"R2"}]
```

- [ ] **Step 2: Run the query tests to verify they fail**

Run: `pytest tests/unit/test_tgraph_query.py -v`
Expected: FAIL because the query package does not exist yet.

- [ ] **Step 3: Implement index-backed query helpers**

```python
def owner_of(graph: TGraph | dict, port_id: str) -> str:
    indexes = ensure_tgraph(graph).build_indexes()
    return indexes.port_owner[port_id]
```

- [ ] **Step 4: Implement graph-level algorithms that F4 can reuse later**

```python
def connected_components(graph: TGraph | dict) -> list[set[str]]:
    ...
```

- [ ] **Step 5: Run the query tests again**

Run: `pytest tests/unit/test_tgraph_query.py tests/unit/test_tgraph_models.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tools/tgraph/query tests/unit/test_tgraph_query.py
git commit -m "feat: add tgraph query helpers"
```

### Task 9: Implement `materialize()` from `logical.v1` to `taal.default.v1`

**Files:**
- Modify: `tools/tgraph/ops/materialize.py`
- Create: `tests/unit/test_tgraph_materialize.py`
- Test: `tests/unit/test_tgraph_materialize.py`

- [ ] **Step 1: Write the failing materialization tests**

```python
from tools.tgraph.ops.materialize import materialize


def test_materialize_promotes_logical_graph_to_taal_profile() -> None:
    logical = {
        "profile": "logical.v1",
        "nodes": [
            {
                "id": "PC1",
                "type": "computer",
                "label": "PC1",
                "ports": [{"id": "PC1:p1", "ip": "10.0.0.10", "cidr": "10.0.0.0/24"}],
                "image": None,
                "flavor": None,
            }
        ],
        "links": [],
    }

    physical = materialize(
        logical,
        target_profile="taal.default.v1",
        defaults={
            "computer": {
                "image": {"id": "ubuntu-22", "name": "Ubuntu 22.04"},
                "flavor": {"vcpu": 2, "ram": 2048, "disk": 20},
            }
        },
    )

    assert physical["profile"] == "taal.default.v1"
    assert physical["nodes"][0]["image"]["id"] == "ubuntu-22"
```

- [ ] **Step 2: Run the materialization tests to verify they fail**

Run: `pytest tests/unit/test_tgraph_materialize.py -v`
Expected: FAIL because `materialize()` is still a pass-through stub.

- [ ] **Step 3: Implement profile promotion and deployment default filling**

```python
def materialize(graph: TGraph | dict, target_profile: str = "taal.default.v1", defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    model = ensure_tgraph(graph)
    ...
```

- [ ] **Step 4: Preserve node, port, and link structure while normalizing image/flavor**

```python
if node.type == "computer":
    image = node.image or defaults["computer"]["image"]
    flavor = node.flavor or defaults["computer"]["flavor"]
else:
    image = None
    flavor = None
```

- [ ] **Step 5: Run the materialization tests again**

Run: `pytest tests/unit/test_tgraph_materialize.py tests/unit/test_tgraph_serialize.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tools/tgraph/ops/materialize.py tests/unit/test_tgraph_materialize.py
git commit -m "feat: add tgraph materialization"
```

### Task 10: Implement patch operations with precise failures and a runtime wrapper

**Files:**
- Modify: `tools/tgraph/ops/patch.py`
- Modify: `validators/patching.py`
- Modify: `tests/unit/test_patch_ops.py`
- Test: `tests/unit/test_patch_ops.py`

- [ ] **Step 1: Rewrite the patch tests around `links` and precise patch failures**

```python
from tools.tgraph.ops.patch import patch
from validators.patching import apply_patch_ops


def test_patch_add_link_returns_updated_graph() -> None:
    result = patch(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "R1", "type": "router", "label": "R1", "ports": [{"id": "R1:p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
                {"id": "PC1", "type": "computer", "label": "PC1", "ports": [{"id": "PC1:p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            ],
            "links": [],
        },
        [{"op": "add_link", "value": {"id": "R1:p1--PC1:p1", "from_port": "R1:p1", "to_port": "PC1:p1", "from_node": "R1", "to_node": "PC1"}, "reason": "connect pc"}],
    )
    assert result.ok is True
    assert result.graph["links"][0]["id"] == "R1:p1--PC1:p1"


def test_patch_rejects_missing_endpoint() -> None:
    result = patch({"profile": "logical.v1", "nodes": [], "links": []}, [{"op": "add_link", "value": {"id": "A:p1--B:p1", "from_port": "A:p1", "to_port": "B:p1"}, "reason": "bad link"}])
    assert result.ok is False
    assert result.issues[0].code == "patch_link_endpoint_not_found"
```

- [ ] **Step 2: Run the patch tests to verify they fail**

Run: `pytest tests/unit/test_patch_ops.py -v`
Expected: FAIL because the current patch helper only appends nodes and edges and does not return precise issues.

- [ ] **Step 3: Implement core patch handling in `tools/tgraph/ops/patch.py`**

```python
class PatchResult(BaseModel):
    ok: bool
    graph: dict[str, Any] | None
    issues: list[ValidationIssue] = Field(default_factory=list)
```

- [ ] **Step 4: Keep `validators/patching.apply_patch_ops()` as a thin runtime adapter**

```python
def apply_patch_ops(graph: dict[str, Any], ops: list[dict[str, Any]]) -> dict[str, Any]:
    result = patch(graph, ops)
    if not result.ok or result.graph is None:
        raise ValueError(result.issues[0].message)
    return result.graph
```

- [ ] **Step 5: Run the patch tests again**

Run: `pytest tests/unit/test_patch_ops.py tests/unit/test_tgraph_validate_consistency.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tools/tgraph/ops/patch.py validators/patching.py tests/unit/test_patch_ops.py
git commit -m "feat: add tgraph patch operations"
```

## Chunk 4: Runtime Alignment, Agent Docs, and Verification

### Task 11: Migrate stage fixtures and guards to profile-aware `nodes/links` payloads

**Files:**
- Modify: `app/container.py`
- Modify: `stages/logical/guard.py`
- Modify: `stages/physical/guard.py`
- Modify: `tests/unit/test_stage_runtime.py`
- Modify: `tests/unit/test_tplan_runner.py`
- Modify: `tests/integration/test_ground_to_logical.py`
- Modify: `tests/integration/test_logical_to_physical.py`
- Test: `tests/unit/test_stage_runtime.py`
- Test: `tests/unit/test_tplan_runner.py`
- Test: `tests/integration/test_ground_to_logical.py`
- Test: `tests/integration/test_logical_to_physical.py`

- [ ] **Step 1: Rewrite the runtime tests to expect profiled `links` payloads**

```python
def test_stage_runtime_persists_logical_profile_payload(fake_runtime) -> None:
    result = fake_runtime.run_stage("logical")
    _artifact_ref, artifact = fake_runtime.artifact_store.read_latest("logical", "tgraph_logical")
    assert artifact["profile"] == "logical.v1"
    assert "links" in artifact
    assert "edges" not in artifact
```

- [ ] **Step 2: Run the runtime and integration tests to verify they fail**

Run: `pytest tests/unit/test_stage_runtime.py tests/unit/test_tplan_runner.py tests/integration/test_ground_to_logical.py tests/integration/test_logical_to_physical.py -v`
Expected: FAIL because fake fixtures, guards, and expected payloads still use `edges` and no `profile` field.

- [ ] **Step 3: Update fake fixtures and stage guards**

```python
def assert_valid(output: LogicalOutput) -> None:
    if output.tgraph_logical.get("profile") != "logical.v1":
        raise ValueError("Logical output must use profile logical.v1.")
```

- [ ] **Step 4: Keep physical fixtures aligned with materialized TAAL outputs**

```python
{"profile": "taal.default.v1", "nodes": [...], "links": [...]}
```

- [ ] **Step 5: Run the runtime and integration tests again**

Run: `pytest tests/unit/test_stage_runtime.py tests/unit/test_tplan_runner.py tests/integration/test_ground_to_logical.py tests/integration/test_logical_to_physical.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/container.py stages/logical/guard.py stages/physical/guard.py tests/unit/test_stage_runtime.py tests/unit/test_tplan_runner.py tests/integration/test_ground_to_logical.py tests/integration/test_logical_to_physical.py
git commit -m "feat: align runtime fixtures with tgraph profiles"
```

### Task 12: Add agent-facing TGraph capability docs

**Files:**
- Create: `tools/tgraph/docs/export.md`
- Create: `tools/tgraph/docs/profiles.md`
- Create: `tools/tgraph/docs/init.md`
- Create: `tools/tgraph/docs/validation.md`
- Create: `tools/tgraph/docs/materialize.md`
- Create: `tools/tgraph/docs/patch.md`
- Create: `tools/tgraph/docs/query.md`

- [ ] **Step 1: Draft the minimal docs skeletons**

```md
# Export

## Purpose
Describe how to export canonical TGraph objects to `logical.v1` and `taal.default.v1` JSON.

## Minimal Example
`{"profile": "logical.v1", "nodes": [], "links": []}`
```
```

- [ ] **Step 2: Write one concise example and common error codes per document**

```md
- `unsupported_export_profile`
- `export_profile_mismatch`
- `export_non_serializable_value`
```

- [ ] **Step 3: Verify the doc set exists and is named consistently**

Run: `rg --files tools/tgraph/docs`
Expected: all seven markdown files are listed exactly once.

- [ ] **Step 4: Commit**

```bash
git add tools/tgraph/docs
git commit -m "docs: add tgraph capability guides"
```

### Task 13: Run the focused verification pass for the TGraph rollout

**Files:**
- Modify only if verification exposes a defect that must be fixed before handoff

- [ ] **Step 1: Run the focused unit suite**

Run: `pytest tests/unit/test_contracts.py tests/unit/test_tgraph_models.py tests/unit/test_tgraph_serialize.py tests/unit/test_tgraph_import.py tests/unit/test_tgraph_validate_schema.py tests/unit/test_tgraph_validate_consistency.py tests/unit/test_tgraph_query.py tests/unit/test_tgraph_materialize.py tests/unit/test_checkpoint_runner.py tests/unit/test_patch_ops.py tests/unit/test_stage_runtime.py tests/unit/test_tplan_runner.py -v`
Expected: PASS

- [ ] **Step 2: Run the focused integration suite**

Run: `pytest tests/integration/test_ground_to_logical.py tests/integration/test_logical_to_physical.py -v`
Expected: PASS

- [ ] **Step 3: Run a manual runtime smoke check**

Run: `python main.py run "PLC1 with HMI1"`
Expected: PASS with a completed run and `logical` / `physical` artifacts that contain `profile`, `nodes`, and `links`.

- [ ] **Step 4: Fix any verification findings before handoff**

```python
# only write code here if one of the verification commands fails
```

- [ ] **Step 5: Commit any verification-driven fixes**

```bash
git add app validators tools tests
git commit -m "test: finalize tgraph core verification"
```

## Notes for execution

- Do not rename `tools/tgraph/model/edge.py` out from under the repo during the first pass; keep it as a compatibility alias while the rest of the code and tests move to `Link` and `links`.
- Keep `validators/tgraph_runner.py` thin. The real validation logic should live under `tools/tgraph/validate/*`.
- Keep `.gml` and `.gns3` import as explicit stubs in this plan. Do not turn this into a dataset adapter project yet.
- Do not add `.gml` or `.gns3` export in this plan. JSON export only.
- Prefer canonical-model helpers over direct dict walking once the new models exist.
- If implementation reveals a spec mismatch, update [2026-03-24-tgraph-design.md](/d:/Paper/10.Domain%20Agent/Trace/docs/superpowers/specs/2026-03-24-tgraph-design.md) first, then continue.

