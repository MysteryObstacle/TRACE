# TRACE TGraph Design

Date: 2026-03-24
Status: Draft approved in conversation, written for review
Scope: `tools/tgraph` as the shared graph core for `logical` and `physical`

## 1. Summary

This document defines the TGraph domain core that connects the `logical` and `physical` stages in TRACE.

TGraph is not only a JSON file format. It is the shared graph layer that owns:

- graph initialization from supported external formats
- canonical graph models used across stages
- validation across format, schema, consistency, and intent layers
- graph materialization from logical topology to physical TAAL topology
- graph patching, graph queries, and reusable graph algorithms
- concise, precise issue reporting for agent repair loops

The primary design decision confirmed in conversation is:

- `logical` produces a lighter logical graph
- `physical` materializes that graph into a complete TAAL topology

Therefore the TGraph design must support multiple graph profiles under one domain boundary rather than forcing one single file shape at every stage.

## 2. Goals

### 2.1 In scope

- Make TGraph the shared domain layer between `logical` and `physical`
- Define one internal graph core with multiple external profiles
- Support JSON as the standard initialization format
- Reserve clean extension points for `.gml` and `.gns3` import
- Validate graphs through layered checks:
  - F1 output format
  - F2 schema
  - F3 consistency
  - F4 intent
- Allow `logical` validation to relax `image` and `flavor`
- Allow `physical` validation to enforce the full TAAL topology contract
- Provide patch, query, and graph algorithm capabilities that later stage validators can reuse
- Return structured, repair-friendly errors to the agent

### 2.2 Out of scope

- Full `.gml` or `.gns3` import implementation in this slice
- Rich auto-repair that silently mutates the graph without explicit ops
- Folding all runtime validator orchestration into `tools/tgraph`
- Replacing stage-specific intent checks with hard-coded global rules

## 3. Current gap in the repository

The current repository contains only a TGraph skeleton:

- `tools/tgraph/model/*` are placeholder dict wrappers
- `tools/tgraph/validate/*` are stubs
- `tools/tgraph/ops/*` are stubs
- `validators/tgraph_runner.py` still assumes an older `nodes` and `edges` shape

This does not yet match the intended topology model:

- top-level `nodes` and `links`
- ports owned by nodes
- profile-aware validation
- stage-aware strictness differences between `logical` and `physical`

This design supersedes the older implicit `nodes` and `edges` assumption for all future TGraph work.

## 4. Core decisions

### 4.1 Domain boundary

`tools/tgraph` is the TGraph domain core. It owns:

- canonical graph models
- import and export adapters
- graph validation logic
- graph materialization
- graph patching
- graph queries and graph algorithms
- agent-facing TGraph capability docs

`validators/` remains a runtime integration layer. It should orchestrate checkpoint execution and normalize reports, but it should not own the real TGraph rules.

### 4.2 Stage graph model split

The confirmed stage boundary is:

- `logical` outputs `logical.v1`
- `physical` outputs `taal.default.v1`

`logical.v1` is a lighter logical graph profile.

`taal.default.v1` is the complete physical topology profile and follows the TAAL schema.

### 4.3 Canonical internal model

All supported inputs should normalize into one internal graph representation before validation, patching, querying, or materialization.

External formats may differ, but the domain core should operate on a stable canonical model with:

- `Node`
- `Port`
- `Link`
- topology-wide indexes such as:
  - node-by-id
  - port-by-id
  - port-owner lookup
  - link-by-id

This keeps `.json`, `.gml`, and `.gns3` import complexity outside the core rule engine.

## 5. Profiles and schemas

### 5.1 TAAL physical topology schema

The physical TAAL topology contract is:

```json
{
  "profile": "taal.default.v1",
  "nodes": [],
  "links": []
}
```

Each node follows:

- `id: string`
- `type: "switch" | "router" | "computer"`
- `label: string`
- `ports: Port[]`
- `image: { "id": string, "name": string } | null`
- `flavor: { "vcpu": int, "ram": int, "disk": int } | null`

Each port follows:

- `id: string`
- `ip: string`
- `cidr: string`

Each link follows:

- `id: string`
- `from_port: string`
- `to_port: string`
- `from_node: string | null`
- `to_node: string | null`

### 5.2 Logical graph profile

The logical graph profile should still use the same high-level `nodes` and `links` structure so stage outputs stay familiar, but it relaxes physical deployment requirements.

Recommended shape:

```json
{
  "profile": "logical.v1",
  "nodes": [],
  "links": []
}
```

`logical.v1` should preserve:

- node IDs
- node type classification
- ports
- links
- optional placeholder deployment fields when useful

`logical.v1` should not require complete `image` and `flavor` data.

### 5.3 Versioning policy

JSON is the standard initialization format.

Profiles should be explicit in the payload and versioned by name:

- `logical.v1`
- `taal.default.v1`

The word `default` belongs to the TAAL profile family and should not replace an explicit version.

Future additions may include:

- `taal.default.v2`
- `taal.gns3.v1`
- `taal.dataset_x.v1`

## 6. Repository structure

Recommended TGraph structure:

```text
tools/
  tgraph/
    __init__.py
    docs/
      init.md
      profiles.md
      validation.md
      materialize.md
      patch.md
      query.md
    io/
      __init__.py
      load.py
      json_loader.py
      gml_loader.py
      gns3_loader.py
    model/
      __init__.py
      tgraph.py
      node.py
      link.py
      port.py
      profiles.py
      indexes.py
    ops/
      __init__.py
      materialize.py
      patch.py
      serialize.py
    query/
      __init__.py
      graph.py
      node.py
      port.py
      path.py
      segment.py
    validate/
      __init__.py
      issues.py
      f1_format.py
      f2_schema.py
      f3_consistency.py
      f4_intent.py
      runner.py
```

The existing `validators/` directory should remain, but only as an application-layer adapter:

```text
validators/
  report.py
  tgraph_runner.py
  patching.py
```

`validators/tgraph_runner.py` should become a thin checkpoint bridge that calls into `tools/tgraph/validate/*`.

## 7. Initialization design

### 7.1 Import entrypoints

The recommended external import API is:

```python
load_tgraph(source, format="auto", target_profile="logical.v1")
load_tgraph_json(source, schema_version="default")
load_tgraph_gml(source, target_profile="logical.v1")
load_tgraph_gns3(source, target_profile="logical.v1")
```

`format="auto"` should dispatch by extension:

- `.json`
- `.gml`
- `.gns3`

### 7.2 Standard behavior

- `.json` is the standard supported initialization format for the first implementation slice
- `.gml` and `.gns3` should have reserved loader entrypoints
- if a non-JSON loader is not implemented yet, it should fail with a stable import error, not with an unhandled runtime exception

Recommended import error codes:

- `unsupported_import_format`
- `import_not_implemented`
- `import_parse_error`

### 7.3 Internal normalization

All imports must normalize into the canonical internal model before they reach:

- validation
- patch
- query
- materialize

This keeps downstream logic profile-aware but format-independent.

## 8. Validation architecture

Validation is split into four layers.

### 8.1 F1: Output format

F1 verifies that the input is structurally parseable as a graph payload.

Examples:

- valid JSON syntax
- top-level object type
- required top-level keys exist

F1 is about file and payload shape, not semantics.

### 8.2 F2: Schema

F2 verifies field-level structure for the active profile.

Checks include:

- required fields exist
- field types are correct
- no unsupported extra fields appear
- `nodes` and `links` entries conform to the target profile

Profile-specific behavior:

- `logical.v1`
  - `image` and `flavor` may be omitted or `null`
- `taal.default.v1`
  - `computer` nodes require non-null `image` and `flavor`
  - non-`computer` nodes must use `null` for `image` and `flavor`

### 8.3 F3: Consistency

F3 verifies semantic consistency after the payload passes schema checks.

Required rules include:

- node IDs are unique
- port IDs are unique across the full topology
- link IDs are unique
- `from_port` and `to_port` reference existing ports
- `link.id` equals `{from_port}--{to_port}`
- `from_node` and `to_node`, if not null, match the owning nodes of their ports
- IPv4 and CIDR strings are valid when present
- switch, router, and computer constraints are enforced

Per-type rules:

- `switch`
  - every `port.ip` must be `""`
  - every `port.cidr` must be non-empty and valid
  - all ports on the same switch must share the same CIDR
- `router`
  - every `port.ip` must be a non-empty valid IPv4 address
  - `port.cidr` may be empty
  - if `port.cidr` is non-empty, the IP must belong to the CIDR and IPs in that CIDR must be unique
- `computer`
  - `port.ip` may be empty or a valid IPv4 address
  - `port.cidr` may be empty
  - if both are non-empty, the IP must belong to the CIDR and IPs in that CIDR must be unique

Recommended stable F3 issue codes include:

- `duplicate_node_id`
- `duplicate_port_id`
- `duplicate_link_id`
- `missing_port_reference`
- `link_id_mismatch`
- `link_node_owner_mismatch`
- `invalid_ip`
- `invalid_cidr`
- `ip_not_in_cidr`
- `duplicate_ip_in_cidr`
- `switch_port_ip_forbidden`
- `switch_cidr_mismatch`
- `computer_image_required`
- `non_computer_image_forbidden`

### 8.4 F4: Intent

F4 verifies higher-level intent requirements and should remain stage-injected rather than hard-coded into the TGraph core.

Examples:

- connectivity requirements
- forbidden link types
- minimum or maximum node counts
- path requirements
- L2 segment consistency

The TGraph core should expose an intent-check entrypoint:

```python
run_intent_checks(graph, rules=[...])
```

The actual intent rules should be supplied by `logical` and `physical` checkpoints.

### 8.5 Validation ownership

The TGraph core should own the real F1-F4 implementations.

The runtime validator layer should only:

- collect checkpoint metadata
- invoke the requested TGraph validator
- load optional script-based checks
- convert results into `ValidationReport`

## 9. Validation issue contract

Issues must be optimized for repair loops. The agent needs one atomic problem at a time with accurate location and a stable error code.

The current repository issue contract should be expanded.

Recommended issue shape:

```python
class ValidationIssue(BaseModel):
    code: str
    message: str
    severity: Literal["error", "warning"]
    scope: Literal["topology", "node", "port", "link", "patch", "intent"]
    targets: list[str] = Field(default_factory=list)
    json_paths: list[str] = Field(default_factory=list)
```

Key design rules:

- `code` must be stable and machine-usable
- `message` must be concise and directly repairable
- `scope` must be specific enough for targeted fixes
- `targets` should use machine-friendly identifiers such as `node:r1` or `port:sw1-p1`
- `json_paths` should point to exact graph locations when possible

Example issue:

```json
{
  "code": "duplicate_port_id",
  "message": "port id 'sw1-p1' is duplicated; port ids must be unique across the topology",
  "severity": "error",
  "scope": "port",
  "targets": ["port:sw1-p1"],
  "json_paths": ["$.nodes[0].ports[0].id", "$.nodes[2].ports[1].id"]
}
```

## 10. Materialization design

`materialize()` converts a logical graph into a full TAAL physical topology.

Primary responsibilities:

- preserve graph structure where possible
- fill `image` and `flavor` for `computer` nodes
- normalize `image` and `flavor` to `null` on non-computer nodes
- derive or backfill `from_node` and `to_node` when needed
- produce a graph that can pass `taal.default.v1` validation

`materialize()` should not:

- silently rewrite unrelated graph topology
- own general intent validation
- replace explicit patch-based repair

Recommended materialization error codes:

- `materialize_missing_image_mapping`
- `materialize_missing_flavor_mapping`
- `materialize_unsupported_node_type`
- `materialize_port_owner_not_found`

API direction:

```python
materialize(graph, target_profile="taal.default.v1", defaults=None)
```

## 11. Patch design

Patch operations should start with a narrow, explicit set rather than generic JSON Patch.

Recommended initial operations:

- `add_node`
- `remove_node`
- `update_node`
- `add_port`
- `remove_port`
- `update_port`
- `add_link`
- `remove_link`
- `update_link`

Patch rules:

- every operation validates its own preconditions
- operation-level failures return precise patch issues
- successful patch application is followed by profile-aware graph validation

Recommended patch error codes:

- `patch_unknown_op`
- `patch_missing_target`
- `patch_duplicate_node_id`
- `patch_duplicate_port_id`
- `patch_link_endpoint_not_found`
- `patch_node_has_attached_links`

Recommended patch result contract:

```python
class PatchResult(BaseModel):
    ok: bool
    graph: dict | None
    issues: list[ValidationIssue] = Field(default_factory=list)
```

This allows patch operations to report actionable failures without throwing opaque runtime exceptions back to the agent.

## 12. Query and graph algorithm design

The query layer should expose a stable, minimal set of high-value helpers that stage validators and intent checks can reuse.

Recommended first-wave query API:

- `get_node(node_id)`
- `get_port(port_id)`
- `neighbors(node_id)`
- `degree(node_id)`
- `ports_of(node_id)`
- `owner_of(port_id)`
- `links_of(node_id_or_port_id)`
- `connected_components()`
- `shortest_path(src_node, dst_node)`
- `nodes_in_cidr(cidr)`
- `ports_in_cidr(cidr)`
- `l2_segments()`

Recommended query error codes:

- `query_node_not_found`
- `query_port_not_found`
- `query_invalid_cidr`
- `query_ambiguous_segment`

The main purpose of this layer is to prevent repeated ad hoc graph scanning inside validator scripts.

## 13. Agent-facing TGraph docs

TGraph capabilities should be documented as separate markdown files under `tools/tgraph/docs/`.

Required initial docs:

- `profiles.md`
- `init.md`
- `validation.md`
- `materialize.md`
- `patch.md`
- `query.md`

Each document should follow the same simple structure:

- purpose
- accepted input
- returned output
- common error codes
- one minimal example
- agent usage guidance

This allows stage prompts or tool docs to attach only the specific TGraph guidance that a stage needs.

## 14. Rollout plan

Implementation should proceed in four slices.

### 14.1 Slice 1: TGraph contracts and profiles

- replace the older `nodes` and `edges` assumption with `nodes` and `links`
- define `logical.v1` and `taal.default.v1`
- add canonical model and indexes
- expand the issue contract so scope and targets are usable for repair

### 14.2 Slice 2: F1-F3 validation core

- implement profile-aware F1, F2, and F3 checks in `tools/tgraph/validate/`
- make `logical.v1` relax `image` and `flavor`
- make `taal.default.v1` enforce the full TAAL rules
- reduce `validators/tgraph_runner.py` to a thin adapter

### 14.3 Slice 3: Materialize, patch, and query

- implement `materialize()` from `logical.v1` to `taal.default.v1`
- implement the initial patch operation set
- implement the reusable query and graph algorithm layer

### 14.4 Slice 4: Stage integration and agent docs

- wire profile-aware validation into `logical` and `physical`
- use the query layer from checkpoint intent checks
- add `tools/tgraph/docs/*.md`

## 15. First implementation recommendation

The highest-value first implementation slice is:

- profile support
- F2 and F3 validation
- runner alignment with the new TGraph contract

This slice should be implemented before broader patching or materialization because it locks in:

- the canonical graph shape
- the stage contract boundary
- the issue format used by every later repair loop

## 16. Final recommendation

TGraph should be implemented as a profile-aware graph domain core rather than a single JSON schema helper.

This gives TRACE:

- a clean boundary between `logical` and `physical`
- reusable graph algorithms for intent checks
- stable repair-oriented validation
- room to add future importers and TAAL profile variants without redesigning the runtime


