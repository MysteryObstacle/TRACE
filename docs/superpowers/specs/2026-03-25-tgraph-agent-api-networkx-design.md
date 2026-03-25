# TRACE TGraph Agent API And NetworkX Adapter Design

Date: 2026-03-25
Status: Draft approved in conversation, written for review
Scope: simplify agent-facing `tgraph` operations while adding a NetworkX-backed graph algorithm layer without giving up `Node`/`Port`/`Link` domain semantics

## 1. Summary

This document refines the `tools/tgraph` design so agents can manipulate topology through a smaller set of semantic operations instead of manually coordinating low-level `node`, `port`, and `link` edits.

The selected design keeps `TGraph` as the canonical source of truth and adds a read-only NetworkX adapter for graph algorithms.

The key decisions confirmed in conversation are:

- `port` remains a real `Node` child resource rather than becoming a pure link implementation detail
- `port.id` is globally unique across the topology
- `node.id` and `port.id` are immutable once created
- agent-facing patch operations should be semantic and topology-oriented
- graph algorithms should be available through stable `tgraph` query helpers rather than by exposing raw NetworkX objects to the agent

## 2. Problem Statement

The current `tgraph` interface makes agents carry too much graph-consistency burden.

Today the agent is effectively required to:

- create ports before creating links
- manually keep node, port, and link edits consistent
- reason about cleanup order when disconnecting or deleting topology pieces
- remember low-level graph invariants that should instead be owned by fixed scripts

This creates a predictable failure mode:

1. the agent intends a simple topology change
2. the change is decomposed into several low-level steps
3. one related object is forgotten or handled in the wrong order
4. validation catches the problem only after the fact

This is especially fragile for operations such as deleting nodes, changing connectivity, or repairing invalid links.

At the same time, the current `tgraph` core is not yet using a mature graph library as its algorithm layer. It relies on Pydantic models plus hand-written indexes and adjacency logic. That is workable for the initial slice, but it will become increasingly expensive as path, connectivity, segmentation, and intent-check workloads grow.

## 3. Goals

### 3.1 In scope

- reduce agent-facing topology manipulation to a small semantic patch API
- keep `port` as a `Node` child resource with `ip` and `cidr` semantics
- keep the canonical persisted shape based on `profile`, `nodes`, and `links`
- preserve stable `Node`/`Port`/`Link` validation boundaries
- add a NetworkX-backed graph algorithm layer without replacing the domain model
- preserve and expand direct query interfaces for `node`, `link`, and `port`
- strengthen patch and query error contracts for repair loops
- update `tgraph` docs plus `logical` and `physical` authoring guidance

### 3.2 Out of scope

- exposing raw NetworkX objects directly to agents
- rewriting the canonical model into a pure graph-library-native structure
- making `port` a first-class graph node in v1 of this redesign
- broad generic JSON Patch support
- silent auto-repair outside explicit semantic operations

## 4. Chosen Design

Three design directions were considered:

1. keep the current `TGraph` shape and only add more low-level patch ops
2. keep `TGraph` as the canonical domain model and add a read-only NetworkX adapter
3. make a graph library the primary source of truth and demote `TGraph` to import/export glue

The selected design is option 2.

This gives the project:

- semantic patch operations that are easy for agents to use
- a stable domain model for serialization and validation
- mature graph algorithms through NetworkX
- direct `node` and `link` query interfaces that do not depend on graph-library internals

## 5. Domain Semantics

### 5.1 Node

`Node` remains the main topology entity and continues to own:

- `id`
- `type`
- `label`
- `ports`
- `image`
- `flavor`

`node.id` is immutable. Renaming a node requires deleting it and creating a new node.

### 5.2 Port

`Port` remains a `Node` child resource and should be interpreted like a physical or logical NIC rather than as a disposable temporary edge endpoint.

This decision is important because `port` carries topology-relevant configuration such as:

- `id`
- `ip`
- `cidr`

`port.id` is globally unique and immutable.

`port` participates in topology links, but its lifecycle is still owned by its parent node rather than by the link layer.

### 5.3 Link

`Link` remains the topology relationship between two ports.

`link` is the only object that changes node-to-node connectivity. Removing a link disconnects topology, but it does not automatically delete either endpoint port.

### 5.4 Connectivity Rule

One `port` may participate in at most one `link`.

This keeps the model aligned with the confirmed semantics that a port is a NIC-like endpoint rather than an arbitrary multi-edge attachment point.

## 6. Agent-Facing Patch API

The agent-facing patch surface should be reduced to six semantic operations:

- `add_nodes`
- `remove_nodes`
- `connect_nodes`
- `disconnect_nodes`
- `update_node`
- `batch_update_nodes`

These operations should be documented as the preferred authoring interface for `logical` and `physical`.

### 6.1 add_nodes

Purpose:

- create one or more nodes with minimal required fields

Minimum required node fields:

- `id`
- `label`
- `type`

Default behavior:

- `ports` defaults to `[]`
- `image` defaults to `null`
- `flavor` defaults to `null`

This operation should support batch addition natively so the agent can create multiple nodes in one patch.

### 6.2 remove_nodes

Purpose:

- delete one or more nodes safely

Required cascading behavior:

- remove all links incident to the removed nodes
- remove all ports owned by the removed nodes

This operation must support batch deletion natively.

The agent should not need to separately delete links and ports first.

### 6.3 connect_nodes

Purpose:

- connect two nodes at specified ports using one semantic operation

Recommended shape:

```json
{
  "op": "connect_nodes",
  "from": {
    "node_id": "PLC1",
    "port": {"id": "PLC1:eth0", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}
  },
  "to": {
    "node_id": "SW1",
    "port": {"id": "SW1:ge0/1", "ip": "", "cidr": "10.0.0.0/24"}
  }
}
```

Behavior:

- if an endpoint port does not exist, create it under the specified node
- if an endpoint port exists, validate its owner and occupancy
- create exactly one link between the two endpoint ports
- derive or normalize the resulting `link.id` deterministically

Failure conditions include:

- endpoint node missing
- endpoint port owned by another node
- endpoint port already linked
- duplicate global `port.id`

### 6.4 disconnect_nodes

Purpose:

- remove one link between two specified node-port endpoints

Recommended shape:

```json
{
  "op": "disconnect_nodes",
  "from": {"node_id": "PLC1", "port_id": "PLC1:eth0"},
  "to": {"node_id": "SW1", "port_id": "SW1:ge0/1"}
}
```

Behavior:

- remove the matching link
- keep both ports intact

This must not implicitly delete ports, because ports are modeled as node-owned NIC-like resources rather than disposable link-owned artifacts.

### 6.5 update_node

Purpose:

- update one node's attributes and child ports through one operation

Recommended shape:

```json
{
  "op": "update_node",
  "node_id": "PLC1",
  "changes": {
    "label": "PLC-1",
    "image": {"id": "openplc-v3", "name": "OpenPLC v3"},
    "ports": [
      {"id": "PLC1:eth0", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}
    ]
  },
  "remove": {
    "ports": ["PLC1:eth2"]
  }
}
```

Rules:

- `changes` and `remove` are both optional, but at least one must be present
- `changes.label`, `changes.type`, `changes.image`, and `changes.flavor` overwrite the existing value if present
- `changes.ports` performs per-port upsert by `port.id`
- `remove.ports` deletes specified ports only if they belong to the target node and are not currently linked

`update_node` must not allow:

- `node.id` rename
- `port.id` rename
- deleting a linked port without first disconnecting it

### 6.6 batch_update_nodes

Purpose:

- apply the same `changes` and `remove` payload shape to multiple target nodes

Rules:

- the payload shape should match `update_node` as closely as possible to reduce agent cognitive load
- execution applies the payload independently to each target node
- if a supplied `port.id` is already owned by another node, the operation must fail with a precise ownership or duplicate error

This keeps the API uniform while still protecting the globally unique port ID invariant.

## 7. Query API

The query layer must remain a first-class part of the design.

The redesign must not improve mutation ergonomics at the cost of losing direct `node` and `link` access.

### 7.1 Direct Object Queries

The query layer should expose stable helpers for domain-object lookup:

- `get_node(node_id)`
- `list_nodes(type=None)`
- `get_link(link_id)`
- `list_links(node_id=None, port_id=None)`
- `get_port(port_id)`
- `ports_of(node_id)`
- `links_of(node_id_or_port_id)`

These helpers should be implemented against canonical `TGraph` indexes rather than against graph-library-native traversal APIs.

### 7.2 Graph Queries

The query layer should also expose algorithmic helpers:

- `neighbors(node_id)`
- `degree(node_id)`
- `connected_components()`
- `shortest_path(src_node, dst_node)`

Future expansion may include:

- `all_simple_paths(...)`
- `bridges()`
- `articulation_points()`
- `nodes_in_cidr(...)`
- `ports_in_cidr(...)`

### 7.3 Query Failure Contract

Query operations should not primarily surface raw Python exceptions to agent-facing tool callers.

Recommended stable error codes include:

- `query_node_not_found`
- `query_link_not_found`
- `query_port_not_found`
- `query_invalid_filter`
- `query_invalid_path_request`

## 8. Internal Architecture

### 8.1 Canonical Source Of Truth

`TGraph` remains the only source of truth.

It owns:

- import and export
- profile-aware model validation
- patch application
- canonical indexes
- issue reporting

It continues to store topology in the domain-native shape:

- top-level `profile`
- top-level `nodes`
- top-level `links`
- `ports` owned by nodes

### 8.2 NetworkX Adapter

NetworkX is added as a read-only graph-algorithm layer rather than as the primary storage model.

Recommended structure:

- `to_networkx(graph) -> nx.MultiGraph`
- or a wrapper such as `TGraphView(graph)` that lazily builds and caches the projected graph

Responsibilities of the adapter:

- build a NetworkX `MultiGraph` view from canonical `TGraph`
- support graph algorithms such as connectivity, pathfinding, and structural analysis
- carry link metadata on edges

Responsibilities that remain outside the adapter:

- mutation
- validation
- serialization
- canonical issue reporting

### 8.3 Projection Rules

The first projection should stay simple:

- NetworkX node = `TGraph` node
- NetworkX edge = `TGraph` link

Recommended edge attributes:

- `link_id`
- `from_port`
- `to_port`
- `from_node`
- `to_node`

This preserves enough topology context for path and connectivity queries while leaving port-specific resource semantics in the canonical domain model.

### 8.4 Why Ports Are Not NetworkX Nodes In V1

The design intentionally does not project ports as graph nodes in the first iteration.

That would turn the topology view into a more complex expanded graph and would make many common node-level algorithms less natural to apply.

Because the main user-facing topology questions remain node-centric, the simpler node-edge projection is preferred for v1.

## 9. Validation And Patch Rules

### 9.1 F2 Schema Requirements

F2 should be extended to validate the new semantic patch shapes:

- `add_nodes` accepts minimal node definitions
- `update_node` uses `node_id`, optional `changes`, and optional `remove`
- `changes.ports` must be a list of port payloads
- `remove.ports` must be a list of strings
- `connect_nodes` and `disconnect_nodes` use explicit endpoint structures

### 9.2 F3 Consistency Requirements

F3 should enforce the confirmed semantic invariants:

- `port.id` is globally unique
- each port belongs to exactly one node
- each port participates in at most one link
- `link.id` is stable and derivable from its endpoints
- no dangling links remain after node removal
- `disconnect_nodes` removes links without deleting ports
- removing a currently linked port is forbidden
- `connect_nodes` must fail rather than silently rewire an already occupied port

### 9.3 Recommended Patch Error Codes

Recommended semantic patch issue codes include:

- `patch_node_not_found`
- `patch_link_not_found`
- `patch_port_not_found`
- `patch_port_owner_mismatch`
- `patch_port_in_use`
- `patch_port_already_linked`
- `patch_disconnect_endpoint_mismatch`
- `patch_remove_connected_port_forbidden`
- `patch_duplicate_port_id`
- `patch_invalid_update_payload`

## 10. Query And View Implementation Split

The redesign should preserve two internal mechanisms under one outward query surface:

1. object queries backed by canonical indexes
2. graph algorithms backed by the NetworkX adapter

This split is important because:

- `get_node`, `get_link`, and `get_port` are domain-object lookups, not graph traversals
- pathfinding and connectivity analysis are graph algorithms and should use mature library implementations

The external `query` API should hide this distinction from the agent.

## 11. Caching Strategy

The NetworkX adapter should be lazily built and invalidated after successful mutation.

Recommended behavior:

- no persisted cache on disk
- build the NetworkX view only when an algorithmic query is requested
- invalidate the view after each successful patch mutation
- allow multiple graph queries in the same runtime step to reuse the cached projection

This keeps the implementation simple while preventing unnecessary repeated projection work.

## 12. Testing Strategy

Tests should be added or updated in four layers.

### 12.1 Patch Unit Tests

- `add_nodes` default-field behavior
- `remove_nodes` cascading link cleanup
- `connect_nodes` automatic port creation
- legal and illegal reuse of existing ports during connect
- `disconnect_nodes` removes link but keeps ports
- `update_node` port upsert behavior
- `update_node.remove.ports` deletes unlinked ports
- deleting linked ports fails
- one port participating in multiple links fails
- `batch_update_nodes` with `ports` and `remove` succeeds or fails correctly per ownership rules

### 12.2 Query Tests

- `get_node`
- `get_link`
- `get_port`
- `list_links(node_id=...)`
- `list_links(port_id=...)`
- `neighbors`
- `connected_components`
- `shortest_path`

### 12.3 Adapter Tests

- canonical `TGraph` projects into the expected NetworkX graph
- edge attributes preserve link and port metadata
- cached views are invalidated correctly after mutation

### 12.4 Prompt And Integration Tests

- `logical` authoring examples use semantic ops instead of manual `add_port` then `add_link`
- `physical` authoring guidance aligns with the new API
- repair loops still behave correctly with the new patch and query error codes

## 13. Documentation Requirements

Documentation is a first-class deliverable of this redesign.

The implementation should update at least:

- `tools/tgraph/docs/patch.md`
- `tools/tgraph/docs/query.md`
- `tools/tgraph/docs/validation.md`
- `tools/tgraph/docs/profiles.md`
- `prompts/logical.md`
- `prompts/physical.md`

Recommended additional docs:

- `tools/tgraph/docs/logical-authoring.md`
- `tools/tgraph/docs/physical-authoring.md`

These docs should explain:

- the preferred semantic patch operations
- the meaning of globally unique `port.id`
- when to use `connect_nodes`
- when to use `update_node`
- why `disconnect_nodes` does not delete ports
- direct node and link query interfaces
- common repair patterns and expected errors

## 14. Final Recommendation

Keep `TGraph` as the canonical domain core, but simplify the agent-facing mutation interface and add a read-only NetworkX adapter for graph algorithms.

In short:

- semantic patch operations replace manual low-level topology choreography
- `port` stays a real node-owned resource with IP and CIDR semantics
- `node`, `link`, and `port` queries remain first-class
- mature graph algorithms become available through a controlled adapter layer
- docs and prompts are updated so agents actually use the new contract

This is the smallest design change that materially reduces agent burden while preserving domain clarity and creating room for stronger graph reasoning.
