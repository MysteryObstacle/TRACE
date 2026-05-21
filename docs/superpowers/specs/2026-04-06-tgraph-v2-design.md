# TGraph v2 Design

## Status

Approved design draft for the next-generation TGraph abstraction in TRACE.

## Background

TRACE currently uses TGraph mainly as a JSON-shaped schema object in stage artifacts, validation, patching, and prompt contracts. That format is suitable for artifact exchange, but it is too thin to serve directly as the runtime topology abstraction needed for:

- topology construction
- topology queries
- graph analysis
- checkpoint compilation
- iterative repair

TGraph v2 separates the exchange format from the runtime graph object while preserving compatibility with the current logical and physical stage flow.

## Goals

TGraph v2 must:

- preserve the current artifact shape used by logical and physical stages
- support safe construction and mutation through a constrained runtime API
- support graph algorithms through NetworkX without making NetworkX the source of truth
- support iterative validation and repair
- preserve benchmark and stage-specific semantic constraints

TGraph v2 is not intended to be a general-purpose graph library.

## Non-Goals

TGraph v2 does not aim to:

- expose raw NetworkX APIs directly to agents
- make NetworkX the primary storage format
- collapse all validation rules into one undifferentiated layer
- allow unconstrained in-place mutation outside a transaction boundary

## Core Model

TGraph v2 is split into two layers.

### TGraphJSON

`TGraphJSON` is the exchange and persistence format.

Responsibilities:

- artifact payload format
- LLM input and output contract
- JSON serialization
- JSON deserialization
- compatibility with current prompts and stage schemas

Canonical top-level shape:

```python
{
    "profile": str,
    "nodes": list[NodeJSON],
    "links": list[LinkJSON],
}
```

`NodeJSON`:

```python
{
    "id": str,
    "type": "switch" | "router" | "computer",
    "label": str,
    "ports": list[PortJSON],
    "image": dict | None,
    "flavor": dict | None,
}
```

`PortJSON`:

```python
{
    "id": str,
    "ip": str,
    "cidr": str,
}
```

`LinkJSON`:

```python
{
    "id": str,
    "from_port": str,
    "to_port": str,
    "from_node": str | None,
    "to_node": str | None,
}
```

Notes:

- `from_port` and `to_port` remain in the schema for compatibility, but links are semantically undirected.
- `from_node` and `to_node` are redundant export fields, not source-of-truth fields.
- normalization may canonicalize endpoint ordering for stable link ids.

### TGraphRuntime

`TGraphRuntime` is the runtime semantic graph built from `TGraphJSON`.

Responsibilities:

- controlled construction and mutation
- topology and semantic queries
- graph analysis
- validation orchestration
- transaction-based editing
- export back to `TGraphJSON`

`TGraphRuntime` is the object used by system code for graph manipulation. `TGraphJSON` remains the object used across stage boundaries.

## Graph Semantics

The topology is semantically an undirected multigraph.

Implications:

- multiple links may exist between the same pair of nodes
- link direction is not semantically meaningful
- a port may participate in at most one link
- NetworkX is used as an algorithm backend, not as the source of truth

Primary algorithm projection:

- `nx.MultiGraph`

Temporary algorithm views:

- when a specific NetworkX algorithm does not directly support `MultiGraph`, the runtime may derive an ephemeral algorithm-specific view
- such derived views are not part of runtime state and are never treated as canonical storage

## Runtime Source of Truth

The runtime layer should keep one canonical semantic state and derive indexes from it.

Recommended runtime storage:

```python
nodes_by_id: dict[str, NodeRecord]
ports_by_id: dict[str, PortRecord]
links_by_id: dict[str, LinkRecord]
```

Recommended derived indexes:

```python
node_ports: dict[str, list[str]]
port_owner: dict[str, str]
port_link: dict[str, str | None]
```

Recommended graph cache:

```python
_nx_multi: nx.MultiGraph
```

Record guidance:

- `NodeRecord` represents node-level fields and port membership
- `PortRecord` includes owner information
- `LinkRecord` stores endpoint ports only
- redundant node endpoint fields are filled during export, not maintained as runtime truth

## Validation Model

Validation remains a four-stage pipeline aligned with the current TRACE design.

### F1: format

Purpose:

- validate whether an input payload has the required top-level JSON shape

Examples:

- payload is not an object
- missing top-level fields
- incorrect top-level field types

### F2: schema

Purpose:

- validate whether `TGraphJSON` can initialize a `TGraphRuntime`
- validate object schema and profile-aware field requirements

Examples:

- invalid node, port, or link field types
- unsupported node types
- malformed image or flavor structures
- invalid profile values

Rule:

- logical stage does not require `computer.image` or `computer.flavor`
- physical stage may require `computer.image` and `computer.flavor`

### F3: consistency

Purpose:

- validate runtime semantic consistency after initialization or mutation

Examples:

- duplicate node ids
- duplicate port ids
- duplicate link ids
- missing endpoint references
- owner mismatches
- link id mismatch after normalization
- invalid IP or CIDR
- switch and router semantic violations
- a port participating in more than one link

This layer is the main place to refine graph invariants and semantic consistency rules.

### F4: intent

Purpose:

- validate higher-level benchmark, checkpoint, and compilation intent

Examples:

- checkpoint selectors do not resolve
- selectors expected to be unique are ambiguous
- checkpoint references stale ids after editing
- topology violates benchmark-specific design intent

## Invariants

The following invariants are part of runtime semantic correctness unless a stage-specific policy explicitly relaxes them.

- node ids are globally unique
- port ids are globally unique
- link ids are globally unique
- every port owner exists
- every link endpoint references an existing port
- each port belongs to exactly one node
- each port belongs to at most one link
- internal indexes agree with canonical runtime storage
- links are semantically undirected
- redundant link node fields, if exported, agree with port ownership

Profile-specific rules such as computer image and flavor requirements are not part of the core invariant set.

## API Design

The runtime API should distinguish between:

- internal runtime methods
- transaction editing primitives
- agent-facing usage

Not every runtime method should be exposed directly to agents.

### Read APIs

```python
get_node(node_id) -> NodeRecord
get_port(port_id) -> PortRecord
get_link(link_id) -> LinkRecord

list_nodes() -> list[str]
list_ports(node_id: str | None = None) -> list[str]
list_links() -> list[str]

get_port_owner(port_id) -> str
list_node_ports(node_id) -> list[str]
get_link_ports(link_id) -> tuple[str, str]
get_peer_port(port_id) -> str | None
get_peer_node(port_id) -> str | None

neighbors(node_id) -> list[str]
incident_links(node_id) -> list[str]
adjacent(node_a, node_b) -> bool
degree(node_id) -> int
```

Naming rule:

- use `get_*` for single-object accessors
- use `list_*` for plural accessors
- use `select_*` for predicate-based queries
- use `add_*`, `update_*`, `remove_*`, `rename_*`, and `rewire_*` for mutations

### Selector APIs

```python
select_nodes(**predicates) -> list[str]
select_ports(**predicates) -> list[str]
select_links(**predicates) -> list[str]

select_one_node(**predicates) -> str | None
select_one_port(**predicates) -> str | None
select_one_link(**predicates) -> str | None
```

Notes:

- `count_*` is intentionally omitted because it is derivable from `len(select_*(...))`
- `select_one_*` is clearer than `select_unique_*` for agent-facing usage

### Graph Analysis APIs

```python
connected(node_a, node_b) -> bool
shortest_path(node_a, node_b) -> list[str]
all_simple_paths(node_a, node_b, cutoff=None) -> list[list[str]]

bridges() -> list[tuple[str, str]]
articulation_points() -> list[str]
cycle_basis() -> list[list[str]]
core_number() -> dict[str, int]
k_core(k=None) -> set[str]
betweenness(node_id: str | None = None) -> dict | float
```

Notes:

- `path_exists` is omitted because it is redundant with `connected` in an undirected topology graph
- analysis methods may use temporary algorithm-specific NetworkX views when needed
- those temporary views are not runtime state

### Conversion APIs

```python
from_json(obj: dict) -> TGraphRuntime
to_json() -> dict
to_networkx() -> nx.MultiGraph
```

`to_networkx()` exists to expose algorithm support, not to transfer ownership of the runtime state.

## Transaction Model

All runtime mutation should flow through an explicit transaction.

The transaction model is not specific to LangGraph nodes. It is the common editing primitive for:

- graph completion
- graph repair
- future interactive editing flows

Example:

```python
tx = graph.begin_transaction()
tx.add_node(...)
tx.add_port(...)
tx.add_link(...)
tx.update_node(...)
tx.update_port(...)
tx.update_link(...)
tx.remove_link(...)
tx.rewire_link(...)

preview = tx.validate(levels=["f1", "f2", "f3"])
result = tx.commit(levels=["f1", "f2", "f3"])
```

Responsibilities of a transaction:

- work against a mutable working copy
- allow temporarily inconsistent intermediate states
- maintain temporary indexes during editing
- validate before commit
- produce a `change_map`
- either commit changes atomically or roll them back

### Commit policy

A transaction should not require passing all `f4` rules by default.

Recommended rule:

- build and iterative repair commits must pass `f1`, `f2`, and `f3`
- `f4` may remain partially unresolved during an iterative loop
- stage finalization or explicit strict validation must require `f1` through `f4`

This allows an agent to fix only part of the issue set, commit that structurally valid change, and continue iterating.

Recommended transaction result shape:

```python
{
    "ok": bool,
    "issues": list[Issue],
    "change_map": dict,
}
```

Recommended `change_map` shape:

```python
{
    "node_ids": {"old": "new"},
    "port_ids": {"old": "new"},
    "link_ids": {"old": "new"},
    "updated_targets": list[str],
}
```

## Repair Model

Repair is an orchestration pattern on top of transactions, not a required core runtime API.

That means:

- the runtime core must support transaction editing
- a higher-level system may optionally provide `repair(...)` convenience wrappers
- if agents already edit the graph by writing Python against transactions, a separate agent-facing `repair()` function is not required

Optional high-level APIs:

```python
repair(issue: Issue, strategy: str | None = None) -> RepairResult
repair_all(issues: list[Issue]) -> list[RepairResult]
```

Repair flow:

1. receive a validator issue or issue subset
2. choose one or more transaction primitives
3. execute them in a transaction
4. validate according to the current commit policy
5. return structured repair output if a wrapper is used

Recommended editing primitives:

- `add_node`
- `add_port`
- `add_link`
- `remove_link`
- `rewire_link`
- `rename_port`
- `rename_link`
- `normalize_link_endpoints`
- `fix_invalid_ip`
- `fix_invalid_cidr`

## Agent Usage

Agents should not carry the full runtime API surface in prompts.

Preferred pattern:

- give the agent a small set of read helpers
- let the agent edit the graph through Python code using a transaction
- keep repair as a workflow concept rather than a mandatory object method

Recommended minimal agent-visible operations:

- `get_node`
- `get_port`
- `get_link`
- `list_nodes`
- `neighbors`
- `select_nodes`
- `select_ports`
- `select_links`
- `validate`
- `begin_transaction`

Within a transaction, the agent can call a small, regular mutation vocabulary:

- `add_*`
- `update_*`
- `remove_*`
- `rename_*`
- `rewire_*`
- `commit()`
- `rollback()`

Agents should not receive direct access to raw NetworkX methods or internal indexes.

## One-Shot Migration Strategy

TGraph v2 should not keep the old functional helper layer and the new runtime layer alive in parallel for long. The recommended direction is a one-shot migration followed by removal of the old layer.

Migration target:

- replace `model.py + patch.py + query.py` with `TGraphJSON + TGraphRuntime + Transaction`
- replace JSON-only validation paths with runtime-aware validation
- move logical and physical build, validate, and repair flows onto runtime and transaction primitives
- remove old functional patch/query entry points after the migration lands

Recommended one-shot migration scope:

- `src/trace/tools/tgraph/`
- `src/trace/stages/logical/prepare.py`
- `src/trace/stages/logical/subgraph.py`
- `src/trace/stages/logical/schemas.py`
- `src/trace/stages/logical/validator.py`
- `src/trace/stages/physical/prepare.py`
- `src/trace/stages/physical/subgraph.py`
- `src/trace/stages/physical/schemas.py`
- `src/trace/stages/physical/validator.py`
- corresponding tests in `tests/unit/tools/tgraph/`, `tests/unit/config/test_prompts.py`, and `tests/integration/test_runtime_pipeline.py`

Target state after migration:

- stage artifacts still exchange `TGraphJSON`
- normalization, validation, and editing all center on `TGraphRuntime`
- build and repair use the same transaction primitives
- old side-door helpers such as `apply_patch_ops()` and standalone `query.py` no longer exist

## Agent / TGraph Tool Protocol

If agents should operate TGraph through Python semantics, the recommended first step is not a general Python sandbox. A safer approach is a thin tool protocol whose implementations call `TGraphRuntime` and `Transaction`.

Recommended protocol:

### Graph Load

```python
tgraph_load(graph_json: dict) -> graph_handle
```

Responsibilities:

- construct `TGraphRuntime` from `TGraphJSON`
- return a handle scoped to the current run, node, or conversation

### Read Operations

```python
tgraph_read(handle, op: str, args: dict | None = None) -> Any
```

Example `op` values:

- `get_node`
- `get_port`
- `get_link`
- `list_nodes`
- `neighbors`
- `select_nodes`
- `validate`

### Begin Transaction

```python
tgraph_begin_tx(handle) -> tx_handle
```

### Transaction Operations

```python
tgraph_tx_apply(tx_handle, op: str, args: dict | None = None) -> Any
```

Example `op` values:

- `add_node`
- `add_port`
- `add_link`
- `update_node`
- `update_port`
- `remove_link`
- `rename_port`
- `rewire_link`

### Commit and Rollback

```python
tgraph_tx_commit(tx_handle, levels: list[str] | None = None) -> dict
tgraph_tx_rollback(tx_handle) -> None
```

The key property of this protocol is:

- the agent experiences Python-like graph manipulation semantics
- the system still exposes only a constrained editing surface
- build and repair can share the same interface
- LangGraph nodes only need to inject graph and transaction handles instead of inventing a second patch language

## Confirmed Design Constraints

- logical stage does not require `computer.image` or `computer.flavor`
- physical-stage validation may require those fields
- topology is semantically an undirected multigraph
- NetworkX exists to provide graph algorithms
- a port may participate in at most one link
- transaction commit does not require full `f4` by default
- repair is transaction-based, and may be represented as a workflow rather than a mandatory runtime method
- one-shot migration is preferred over long-lived dual maintenance
- agents should operate runtime and transactions through a thin tool protocol rather than arbitrary Python execution

## Summary

TGraph v2 preserves the current JSON artifact contract while introducing a true runtime semantic graph for controlled mutation, validation, analysis, and iterative repair. The central design choice is to separate exchange format from runtime behavior without changing the external topology shape expected by TRACE stages.
