# TGraph Agent API And NetworkX Adapter Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace low-level agent-managed `tgraph` mutations with a semantic patch/query API, add a read-only NetworkX adapter for graph algorithms, and update validation, prompts, tests, and docs to match the new contract.

**Architecture:** Keep `TGraph` as the only persisted source of truth and layer semantic patch operations plus stable direct-object queries on top of it. Add a lazy NetworkX `MultiGraph` projection for connectivity and path algorithms, while preserving node/link/port lookups through canonical indexes and migrating authoring docs/prompts to the new surface.

**Tech Stack:** Python 3.10+, Pydantic v2, NetworkX 3.4.x, pytest, existing TRACE runtime and prompt system, local Conda env `Trace`.

---

**Execution notes:** Use `@test-driven-development` for each task, run tests with `conda run -n Trace ...`, and use `@verification-before-completion` before claiming the rollout is done.

## File Map

**Create:**
- `tools/tgraph/graph_view.py`
- `tools/tgraph/query/link.py`
- `tools/tgraph/docs/logical-authoring.md`
- `tools/tgraph/docs/physical-authoring.md`
- `tests/unit/test_tgraph_graph_view.py`

**Modify:**
- `tools/tgraph/ops/patch.py`
- `validators/patching.py`
- `tools/tgraph/model/tgraph.py`
- `tools/tgraph/model/indexes.py`
- `tools/tgraph/query/__init__.py`
- `tools/tgraph/query/node.py`
- `tools/tgraph/query/graph.py`
- `tools/tgraph/query/port.py`
- `tools/tgraph/validate/f2_schema.py`
- `tools/tgraph/validate/f3_consistency.py`
- `tools/tgraph/docs/patch.md`
- `tools/tgraph/docs/query.md`
- `tools/tgraph/docs/validation.md`
- `tools/tgraph/docs/profiles.md`
- `prompts/logical.md`
- `prompts/physical.md`
- `tests/unit/test_patch_ops.py`
- `tests/unit/test_tgraph_query.py`
- `tests/unit/test_tgraph_validate_consistency.py`
- `tests/integration/test_patch_first_logical.py`
- `tests/integration/test_patch_first_physical.py`

**Responsibility notes:**
- `tools/tgraph/ops/patch.py` owns semantic patch application and structured patch failures.
- `tools/tgraph/query/*` owns agent-safe query helpers; direct object lookups stay index-backed.
- `tools/tgraph/graph_view.py` owns the lazy NetworkX projection and cache invalidation rules.
- `tools/tgraph/validate/*` owns the new patch/query invariants such as global port uniqueness and `port_degree <= 1`.
- `prompts/*` and `tools/tgraph/docs/*` must be updated together so agents actually use the new API.

## Chunk 1: Semantic Patch API

### Task 1: Lock the new patch contract with failing tests

**Files:**
- Modify: `tests/unit/test_patch_ops.py`
- Test: `tests/unit/test_patch_ops.py`

- [ ] **Step 1: Add failing tests for the new semantic operations**

```python
def test_patch_connect_nodes_creates_missing_ports_and_link() -> None:
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [], "image": None, "flavor": None},
            {"id": "SW1", "type": "switch", "label": "SW1", "ports": [], "image": None, "flavor": None},
        ],
        "links": [],
    }

    result = patch(
        graph,
        [
            {
                "op": "connect_nodes",
                "from": {"node_id": "PLC1", "port": {"id": "PLC1:eth0", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}},
                "to": {"node_id": "SW1", "port": {"id": "SW1:ge0/1", "ip": "", "cidr": "10.0.0.0/24"}},
            }
        ],
    )

    assert result.ok is True
    assert {port["id"] for port in result.graph["nodes"][0]["ports"]} == {"PLC1:eth0"}
    assert result.graph["links"][0]["id"] == "PLC1:eth0--SW1:ge0/1"


def test_patch_disconnect_nodes_removes_link_but_keeps_ports() -> None:
    ...


def test_update_node_remove_ports_rejects_connected_port() -> None:
    ...


def test_batch_update_nodes_accepts_changes_and_remove() -> None:
    ...
```

- [ ] **Step 2: Run the focused patch tests to verify they fail**

Run: `conda run -n Trace pytest tests/unit/test_patch_ops.py -v`
Expected: FAIL because `patch()` still exposes low-level `add_port` / `add_link` semantics and does not know `connect_nodes`, `disconnect_nodes`, or `remove.ports`.

- [ ] **Step 3: Add one failure-case test for the global port-ID invariant**

```python
def test_batch_update_nodes_rejects_port_id_owned_by_other_node() -> None:
    ...
    assert result.issues[0].code in {"patch_port_owner_mismatch", "patch_duplicate_port_id"}
```

- [ ] **Step 4: Re-run the patch tests**

Run: `conda run -n Trace pytest tests/unit/test_patch_ops.py -v`
Expected: FAIL only on the newly added semantic behaviors.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_patch_ops.py
git commit -m "test: lock tgraph semantic patch api"
```

### Task 2: Implement the semantic patch operations and keep the runtime wrapper thin

**Files:**
- Modify: `tools/tgraph/ops/patch.py`
- Modify: `validators/patching.py`
- Test: `tests/unit/test_patch_ops.py`

- [ ] **Step 1: Replace low-level patch dispatch with the six semantic ops**

Implement support for:

- `add_nodes`
- `remove_nodes`
- `connect_nodes`
- `disconnect_nodes`
- `update_node`
- `batch_update_nodes`

Keep any legacy low-level ops only as temporary compatibility shims if existing tests still depend on them.

- [ ] **Step 2: Implement `update_node` with `changes` plus `remove`**

Use behavior like:

```python
if "ports" in changes:
    upsert_ports(...)
if "ports" in remove:
    remove_ports(...)
```

Rules:

- `node.id` immutable
- `port.id` immutable
- remove of linked ports forbidden

- [ ] **Step 3: Implement `connect_nodes` and `disconnect_nodes`**

`connect_nodes` must:

- create missing endpoint ports
- verify existing endpoint owner
- reject already-linked ports
- create exactly one link

`disconnect_nodes` must:

- locate the exact link by endpoint ports
- delete only the link
- keep both ports

- [ ] **Step 4: Keep `validators/patching.py` as a thin adapter**

Expected shape:

```python
def apply_patch_ops(graph: dict[str, Any], ops: list[dict[str, Any]]) -> dict[str, Any]:
    result = patch(graph, ops)
    if not result.ok or result.graph is None:
        raise ValueError(result.issues[0].message)
    return result.graph
```

- [ ] **Step 5: Run the focused patch tests**

Run: `conda run -n Trace pytest tests/unit/test_patch_ops.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tools/tgraph/ops/patch.py validators/patching.py tests/unit/test_patch_ops.py
git commit -m "feat: add semantic tgraph patch operations"
```

## Chunk 2: Query Layer And NetworkX Adapter

### Task 3: Lock direct node/link/port query helpers with failing tests

**Files:**
- Modify: `tests/unit/test_tgraph_query.py`
- Create: `tools/tgraph/query/link.py`
- Test: `tests/unit/test_tgraph_query.py`

- [ ] **Step 1: Add failing tests for direct object queries**

```python
def test_get_link_returns_the_exact_link() -> None:
    graph = {
        "profile": "logical.v1",
        "nodes": [...],
        "links": [
            {"id": "PLC1:eth0--SW1:ge0/1", "from_port": "PLC1:eth0", "to_port": "SW1:ge0/1", "from_node": "PLC1", "to_node": "SW1"}
        ],
    }
    link = get_link(graph, "PLC1:eth0--SW1:ge0/1")
    assert link.id == "PLC1:eth0--SW1:ge0/1"


def test_list_links_supports_node_and_port_filters() -> None:
    ...
```

- [ ] **Step 2: Add one failure test for query errors**

```python
def test_get_link_raises_stable_code_when_missing() -> None:
    with pytest.raises(KeyError, match="query_link_not_found:missing"):
        get_link({"profile": "logical.v1", "nodes": [], "links": []}, "missing")
```

- [ ] **Step 3: Run the query tests to verify they fail**

Run: `conda run -n Trace pytest tests/unit/test_tgraph_query.py -v`
Expected: FAIL because `get_link()` and `list_links()` do not exist yet.

- [ ] **Step 4: Re-run the same tests after confirming the failure surface**

Run: `conda run -n Trace pytest tests/unit/test_tgraph_query.py -v`
Expected: still FAIL, now with only the newly added query expectations.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_tgraph_query.py
git commit -m "test: lock tgraph node and link queries"
```

### Task 4: Implement index-backed direct queries and the lazy NetworkX view

**Files:**
- Create: `tools/tgraph/graph_view.py`
- Modify: `tools/tgraph/model/tgraph.py`
- Modify: `tools/tgraph/model/indexes.py`
- Modify: `tools/tgraph/query/__init__.py`
- Modify: `tools/tgraph/query/node.py`
- Modify: `tools/tgraph/query/graph.py`
- Modify: `tools/tgraph/query/port.py`
- Create: `tools/tgraph/query/link.py`
- Create: `tests/unit/test_tgraph_graph_view.py`
- Test: `tests/unit/test_tgraph_query.py`
- Test: `tests/unit/test_tgraph_graph_view.py`

- [ ] **Step 1: Implement direct link queries using canonical indexes**

Add helpers such as:

```python
def get_link(graph: TGraph | dict, link_id: str) -> Link:
    ...


def list_links(graph: TGraph | dict, node_id: str | None = None, port_id: str | None = None) -> list[Link]:
    ...
```

- [ ] **Step 2: Add failing tests for the NetworkX projection**

```python
def test_to_networkx_preserves_link_metadata() -> None:
    view = to_networkx(sample_graph())
    edge_data = next(iter(view.edges(data=True, keys=True)))
    assert edge_data[3]["link_id"] == "PLC1:eth0--SW1:ge0/1"
    assert edge_data[3]["from_port"] == "PLC1:eth0"
```

- [ ] **Step 3: Implement the lazy adapter**

Use a simple cached builder:

```python
def to_networkx(graph: TGraph | dict) -> nx.MultiGraph:
    ...
```

The projection rules are:

- NetworkX node = `TGraph` node
- NetworkX edge = `TGraph` link
- edge attrs keep `link_id`, `from_port`, `to_port`, `from_node`, `to_node`

- [ ] **Step 4: Make algorithmic query helpers call the adapter**

Wire:

- `neighbors`
- `degree`
- `connected_components`
- `shortest_path`

through the NetworkX projection, while keeping `get_node` / `get_link` / `get_port` index-backed.

- [ ] **Step 5: Run the query and graph-view tests**

Run: `conda run -n Trace pytest tests/unit/test_tgraph_query.py tests/unit/test_tgraph_graph_view.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tools/tgraph/graph_view.py tools/tgraph/model/tgraph.py tools/tgraph/model/indexes.py tools/tgraph/query tests/unit/test_tgraph_query.py tests/unit/test_tgraph_graph_view.py
git commit -m "feat: add tgraph queries and networkx adapter"
```

## Chunk 3: Validation, Prompts, And Authoring Docs

### Task 5: Strengthen F2 and F3 for the new patch invariants

**Files:**
- Modify: `tools/tgraph/validate/f2_schema.py`
- Modify: `tools/tgraph/validate/f3_consistency.py`
- Modify: `tests/unit/test_tgraph_validate_consistency.py`
- Test: `tests/unit/test_tgraph_validate_consistency.py`

- [ ] **Step 1: Add failing tests for the new invariants**

```python
def test_f3_rejects_port_linked_more_than_once() -> None:
    issues = f3_consistency(
        {
            "profile": "logical.v1",
            "nodes": [...],
            "links": [
                {"id": "PLC1:eth0--SW1:ge0/1", ...},
                {"id": "PLC1:eth0--RTR1:ge0/0", ...},
            ],
        }
    )
    assert {issue["code"] for issue in issues} >= {"patch_port_already_linked", "port_degree_exceeded"}
```

- [ ] **Step 2: Add a failing schema test for `update_node` payload shape if schema helpers validate patch bodies**

If patch-body schema validation lives outside F2, write this as a patch-op unit test instead and document that split inside the test file.

- [ ] **Step 3: Run the focused validation tests**

Run: `conda run -n Trace pytest tests/unit/test_tgraph_validate_consistency.py -v`
Expected: FAIL because the current consistency layer does not enforce `port_degree <= 1`.

- [ ] **Step 4: Implement the minimal validation changes**

Add checks for:

- global `port.id` uniqueness
- one-owner-per-port
- at-most-one-link-per-port
- removal of linked ports forbidden through patch logic
- stable error codes for semantic failures

- [ ] **Step 5: Run the validation and patch suites**

Run: `conda run -n Trace pytest tests/unit/test_tgraph_validate_consistency.py tests/unit/test_patch_ops.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tools/tgraph/validate/f2_schema.py tools/tgraph/validate/f3_consistency.py tests/unit/test_tgraph_validate_consistency.py tests/unit/test_patch_ops.py
git commit -m "feat: enforce semantic tgraph invariants"
```

### Task 6: Rewrite prompts and `tgraph` docs around the semantic API

**Files:**
- Modify: `prompts/logical.md`
- Modify: `prompts/physical.md`
- Modify: `tools/tgraph/docs/patch.md`
- Modify: `tools/tgraph/docs/query.md`
- Modify: `tools/tgraph/docs/validation.md`
- Modify: `tools/tgraph/docs/profiles.md`
- Create: `tools/tgraph/docs/logical-authoring.md`
- Create: `tools/tgraph/docs/physical-authoring.md`
- Test: `tests/integration/test_patch_first_logical.py`
- Test: `tests/integration/test_patch_first_physical.py`

- [ ] **Step 1: Add prompt-alignment assertions before editing prompt text**

Add one assertion per stage that checks:

- semantic ops are present
- low-level `add_port` + `add_link` choreography is no longer the primary example
- node/link queries are described

- [ ] **Step 2: Rewrite the logical and physical prompts**

Make the prompt examples prefer:

- `connect_nodes`
- `disconnect_nodes`
- `update_node`
- `batch_update_nodes`

Also document:

- globally unique `port.id`
- `disconnect_nodes` does not delete ports
- node and link query helpers stay available

- [ ] **Step 3: Update `tgraph` docs**

Refresh:

- `patch.md`
- `query.md`
- `validation.md`
- `profiles.md`

Create:

- `logical-authoring.md`
- `physical-authoring.md`

Each doc should include at least one example and the most relevant error codes.

- [ ] **Step 4: Run the prompt-facing integration tests**

Run: `conda run -n Trace pytest tests/integration/test_patch_first_logical.py tests/integration/test_patch_first_physical.py -v`
Expected: FAIL first on prompt drift, then PASS after prompt/docs updates land.

- [ ] **Step 5: Re-run the same integration tests**

Run: `conda run -n Trace pytest tests/integration/test_patch_first_logical.py tests/integration/test_patch_first_physical.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add prompts/logical.md prompts/physical.md tools/tgraph/docs tests/integration/test_patch_first_logical.py tests/integration/test_patch_first_physical.py
git commit -m "docs: migrate tgraph authoring to semantic api"
```

## Chunk 4: Integration And Verification

### Task 7: Update integration fixtures and regression expectations for the new contract

**Files:**
- Modify: `tests/integration/test_patch_first_logical.py`
- Modify: `tests/integration/test_patch_first_physical.py`
- Test: `tests/integration/test_patch_first_logical.py`
- Test: `tests/integration/test_patch_first_physical.py`

- [ ] **Step 1: Add or adjust failing integration cases for node removal and disconnect behavior**

Cover:

- node deletion cascades links and owned ports
- disconnect keeps ports intact
- batch node updates with `ports/remove` behave per-node

- [ ] **Step 2: Run the integration tests to verify they fail**

Run: `conda run -n Trace pytest tests/integration/test_patch_first_logical.py tests/integration/test_patch_first_physical.py -v`
Expected: FAIL because existing fixtures still reflect the low-level patch surface.

- [ ] **Step 3: Update the integration fixtures and expectations**

Make the fixture payloads and assertions match the new semantic ops and error codes.

- [ ] **Step 4: Re-run the integration tests**

Run: `conda run -n Trace pytest tests/integration/test_patch_first_logical.py tests/integration/test_patch_first_physical.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_patch_first_logical.py tests/integration/test_patch_first_physical.py
git commit -m "test: align patch-first flows with semantic tgraph api"
```

### Task 8: Run focused verification before implementation handoff

**Files:**
- Modify only if verification exposes defects

- [ ] **Step 1: Run the focused unit suites**

Run: `conda run -n Trace pytest tests/unit/test_patch_ops.py tests/unit/test_tgraph_query.py tests/unit/test_tgraph_graph_view.py tests/unit/test_tgraph_validate_consistency.py -v`
Expected: PASS

- [ ] **Step 2: Run the focused integration suites**

Run: `conda run -n Trace pytest tests/integration/test_patch_first_logical.py tests/integration/test_patch_first_physical.py -v`
Expected: PASS

- [ ] **Step 3: Run one broader regression slice**

Run: `conda run -n Trace pytest tests/unit/test_stage_runtime.py tests/unit/test_checkpoint_runner.py tests/integration/test_ground_to_logical.py tests/integration/test_logical_to_physical.py -v`
Expected: PASS, or clearly identified unrelated failures.

- [ ] **Step 4: Fix any verification findings before handoff**

Only add code here if one of the verification commands fails.

- [ ] **Step 5: Commit verification-driven fixes**

```bash
git add tools/tgraph validators prompts tests
git commit -m "test: finalize semantic tgraph rollout"
```

## Notes For Execution

- Keep `TGraph` as the only persisted source of truth; do not let the NetworkX adapter become a hidden mutation path.
- Direct `node`, `link`, and `port` lookups should stay index-backed even after algorithmic queries move to NetworkX.
- `batch_update_nodes` may accept `ports` and `remove`, but global `port.id` ownership rules must still be enforced strictly.
- `disconnect_nodes` must never delete ports implicitly.
- If implementation reveals a mismatch with the approved spec, update [2026-03-25-tgraph-agent-api-networkx-design.md](/d:/Paper/10.Domain%20Agent/Trace/docs/superpowers/specs/2026-03-25-tgraph-agent-api-networkx-design.md) first, then continue.
