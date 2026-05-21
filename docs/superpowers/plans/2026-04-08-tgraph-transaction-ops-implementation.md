# TGraph Transaction Ops Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add node/link editing operations to TGraph transactions and the agent tool protocol, with port updates handled only through `add_link` and `update_node` (existing ports only, no port add/remove via `update_node`).

**Architecture:** Extend `TGraphTransaction` with `add_node`, `update_node`, `remove_link`, `remove_node`. `add_link` already supports creating or updating ports (ip/cidr only) when node ids are supplied. Update `BoundTGraphTools.tx_apply` to accept the new ops. Add unit tests to lock behavior (including port update rules, no port add/remove via `update_node`, and error cases).

**Tech Stack:** Python 3.11, pytest, pydantic, langchain-core tools.

---

## File Structure

- Modify: `src/trace/tools/tgraph/transaction.py`
  - Add `add_node`, `update_node`, `remove_link`, `remove_node`
  - Adjust existing `_ensure_endpoint` to support port updates via `add_link`
- Modify: `src/trace/tools/tgraph/protocol.py`
  - Expand `tx_apply` to handle new ops
  - Update tool description to reflect new operations and port update rules
- Modify: `tests/unit/tools/tgraph/test_graph_core.py`
  - Add tests for new transaction ops and edge cases

---

## Chunk 1: Transaction Ops (Core Behavior)

### Task 1: Add tests for new transaction operations

**Files:**
- Modify: `tests/unit/tools/tgraph/test_graph_core.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_transaction_add_node_and_update_node_ports():
    runtime = TGraphRuntime.from_json({"profile": "logical.v1", "nodes": [], "links": []})
    tx = runtime.begin_transaction()
    tx.add_node("r1", "router", "R1")
    tx.add_node("r2", "router", "R2")
    tx.add_link("r1:p1", "r2:p1", from_node="r1", to_node="r2", from_ip="10.0.0.1", from_cidr="10.0.0.0/30", to_ip="10.0.0.2", to_cidr="10.0.0.0/30")
    tx.commit()

    tx = runtime.begin_transaction()
    tx.update_node("r1", ports=[{"id": "r1:p1", "ip": "10.0.0.3"}])
    result = tx.commit()

    assert result["ok"] is True
    assert runtime.get_node("r1")["ports"][0]["ip"] == "10.0.0.3"


def test_update_node_rejects_unknown_port_id():
    runtime = TGraphRuntime.from_json({"profile": "logical.v1", "nodes": [{"id": "r1", "type": "router", "label": "R1", "ports": []}], "links": []})
    tx = runtime.begin_transaction()
    with pytest.raises(KeyError):
        tx.update_node("r1", ports=[{"id": "r1:p9", "ip": "10.0.0.9"}])


def test_update_node_cannot_change_port_id():
    runtime = TGraphRuntime.from_json({
        "profile": "logical.v1",
        "nodes": [
            {"id": "r1", "type": "router", "label": "R1", "ports": [{"id": "r1:p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}]},
        ],
        "links": [],
    })
    tx = runtime.begin_transaction()
    with pytest.raises(KeyError):
        tx.update_node("r1", ports=[{"id": "r1:p9", "ip": "10.0.0.9"}])


def test_add_link_can_create_ports_with_node_ids():
    runtime = TGraphRuntime.from_json({
        "profile": "logical.v1",
        "nodes": [
            {"id": "r1", "type": "router", "label": "R1", "ports": []},
            {"id": "r2", "type": "router", "label": "R2", "ports": []},
        ],
        "links": [],
    })
    tx = runtime.begin_transaction()
    tx.add_link("r1:p1", "r2:p1", from_node="r1", to_node="r2", from_ip="10.0.0.1", from_cidr="10.0.0.0/30", to_ip="10.0.0.2", to_cidr="10.0.0.0/30")
    result = tx.commit(levels=["f1", "f2", "f3"])
    assert result["ok"] is True


def test_remove_link_does_not_delete_ports():
    runtime = TGraphRuntime.from_json({
        "profile": "logical.v1",
        "nodes": [
            {"id": "r1", "type": "router", "label": "R1", "ports": [{"id": "r1:p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}]},
            {"id": "r2", "type": "router", "label": "R2", "ports": [{"id": "r2:p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/30"}]},
        ],
        "links": [{"id": "r1:p1--r2:p1", "from_port": "r1:p1", "to_port": "r2:p1"}],
    })
    tx = runtime.begin_transaction()
    tx.remove_link("r1:p1--r2:p1")
    result = tx.commit(levels=["f1", "f2", "f3"])
    assert result["ok"] is True
    assert runtime.to_json()["links"] == []
    assert len(runtime.to_json()["nodes"][0]["ports"]) == 1


def test_remove_node_cascade_removes_links_and_ports():
    runtime = TGraphRuntime.from_json({
        "profile": "logical.v1",
        "nodes": [
            {"id": "r1", "type": "router", "label": "R1", "ports": [{"id": "r1:p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}]},
            {"id": "r2", "type": "router", "label": "R2", "ports": [{"id": "r2:p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/30"}]},
        ],
        "links": [{"id": "r1:p1--r2:p1", "from_port": "r1:p1", "to_port": "r2:p1"}],
    })
    tx = runtime.begin_transaction()
    tx.remove_node("r1", cascade=True)
    result = tx.commit(levels=["f1", "f2", "f3"])
    assert result["ok"] is True
    assert [n["id"] for n in runtime.to_json()["nodes"]] == ["r2"]
    assert runtime.to_json()["links"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/tools/tgraph/test_graph_core.py::test_transaction_add_node_and_update_node_ports -v`  
Expected: FAIL with “AttributeError: add_node/update_node/remove_link/remove_node not found”

- [ ] **Step 3: Implement minimal transaction logic**

Add:
- `add_node`
- `update_node` (ports partial update, error on unknown port id, no port add/remove)
- `remove_link`
- `remove_node` (cascade behavior)

Implement port update in `update_node`:
```python
def update_node(self, node_id, **attrs):
    ports = attrs.pop("ports", None)
    # update node fields
    # if ports: for each port update ip/cidr only; raise if port id missing
    # do not allow changing port id, do not allow adding/removing ports
```

Implement cascade removal:
```python
def remove_node(self, node_id, cascade=True):
    # remove incident links if cascade
    # remove node and its ports
```

- [ ] **Step 4: Run the unit tests again**

Run: `pytest tests/unit/tools/tgraph/test_graph_core.py -k "transaction_add_node or update_node or remove_link or remove_node" -q`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/unit/tools/tgraph/test_graph_core.py src/trace/tools/tgraph/transaction.py
git commit -m "feat(tgraph): add node/link transaction ops"
```

## Chunk 2: Tool Protocol (`tx_apply`) Updates

### Task 2: Expand BoundTGraphTools to accept new ops

**Files:**
- Modify: `src/trace/tools/tgraph/protocol.py`

- [ ] **Step 1: Write a failing test**

```python
def test_bound_tgraph_tools_supports_add_node_and_remove_node():
    tools = BoundTGraphTools.from_json({"profile": "logical.v1", "nodes": [], "links": []})
    tools.begin_tx()
    tools.tx_apply("add_node", {"node_id": "r1", "type": "router", "label": "R1"})
    result = tools.tx_commit(["f1", "f2", "f3"])
    assert result["ok"] is True
    assert tools.topology_view()["nodes"] == ["r1"]
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `pytest tests/unit/tools/tgraph/test_graph_core.py::test_bound_tgraph_tools_supports_add_node_and_remove_node -v`  
Expected: FAIL with “unsupported tgraph transaction op”

- [ ] **Step 3: Implement op dispatch**

Update `tx_apply`:
- `add_node` -> `transaction.add_node(...)`
- `update_node` -> `transaction.update_node(...)`
- `add_link` -> existing behavior
- `remove_link` -> `transaction.remove_link(...)`
- `remove_node` -> `transaction.remove_node(...)`

Update the tool description string to list supported ops and port update rules.

- [ ] **Step 4: Re-run the tests**

Run: `pytest tests/unit/tools/tgraph/test_graph_core.py -k "bound_tgraph_tools_supports_add_node" -q`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/unit/tools/tgraph/test_graph_core.py src/trace/tools/tgraph/protocol.py
git commit -m "feat(tgraph): expand tx_apply ops for nodes and links"
```

---

## Chunk 3: Full Regression

### Task 3: Run full test suite

- [ ] **Step 1: Run full suite**

Run: `pytest -q`  
Expected: PASS

- [ ] **Step 2: Commit (if any fixes)**

```bash
git add -A
git commit -m "test: update for tgraph node/link ops"
```

---

## Plan Review Loop

This plan requires a plan-document-reviewer subagent per chunk. If subagents are unavailable in this environment, proceed without the review loop and note the limitation in the execution summary.
