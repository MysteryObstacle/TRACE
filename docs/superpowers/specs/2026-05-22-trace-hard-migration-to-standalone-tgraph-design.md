# TRACE Hard Migration To Standalone TGraph Design

## Summary

TRACE will stop carrying a legacy TGraph compatibility layer. TRACE keeps its workflow identity as `ground -> logical -> physical`, but every logical and physical stage artifact will use the standalone `tgraph` IR and operation APIs directly.

The goal is a clean split:

- `tgraph` owns IR, graph operations, validation, inspection, IO, target placeholders, and agent-facing contracts.
- `trace` owns workflow orchestration, stage transitions, knowledge/image/catalog decisions, and how user intent is turned into graph patches and checkpoints.

This is a hard migration. We do not keep old `TGraphJSON`, `profile`, `TGraphRuntime`, transaction, or `tgraph_logical` / `tgraph_physical` compatibility behavior in active code.

## Current Problem

The first standalone TGraph refactor added `src/tgraph` while keeping adapters in `src/trace/tools/tgraph`. That was useful for a safe first step, but it leaves two concepts of TGraph in the project:

- New canonical TGraph documents:

```json
{"stage": "logical", "nodes": [], "links": []}
```

- Old TRACE graph envelopes:

```json
{"profile": "logical.v1", "nodes": [], "links": []}
```

The adapter layer also preserves names such as `TGraphJSON`, `TGraphRuntime`, `transaction`, `tgraph_logical`, and `tgraph_physical`. These names make agents and maintainers continue thinking in the old model.

## Goals

- Keep TRACE workflow as `ground -> logical -> physical`.
- Use standalone `tgraph.TGraph` as the only graph model.
- Use batch patch as the only public graph mutation protocol.
- Use new canonical graph shape with `stage`, `nodes`, and `links`.
- Replace stage artifact internals with `graph`, `checkpoints`, and `validator_script`.
- Move F4 checkpoint/script execution into TGraph validation capabilities.
- Give validator scripts a stable read-only graph SDK.
- Provide an agent capability contract explaining what TGraph can express directly and how to translate unsupported IaC requests.
- Remove active imports of `trace.tools.tgraph.*` from TRACE stage code and skill scripts.

## Non-Goals

- Do not change TRACE's top-level workflow stages.
- Do not implement real Terraform/Pulumi/TOSCA generation in this migration.
- Do not add domain knowledge, image catalog lookup, provider catalog lookup, or workflow planning into TGraph.
- Do not model higher-level network objects such as `segment`, `zone`, `software`, `packages`, or firewall rules inside the TGraph graph document.

## Stage Artifact Shape

TRACE stage artifacts use one common shape:

```json
{
  "graph": {
    "stage": "logical",
    "nodes": [],
    "links": []
  },
  "checkpoints": [],
  "validator_script": null
}
```

For the physical stage, `graph.stage` is `"physical"`.

`logical_artifact` and `physical_artifact` remain as TRACE workflow boundaries. Inside each artifact, field names are no longer stage-specific. There is no `tgraph_logical`, no `tgraph_physical`, and no `profile`.

Suggested schema:

```python
class StageArtifact(BaseModel):
    graph: TGraph
    checkpoints: list[Checkpoint] = Field(default_factory=list)
    validator_script: str | None = None


class LogicalArtifact(StageArtifact): ...


class PhysicalArtifact(StageArtifact): ...
```

The stage classes may add validators that assert `graph.stage == "logical"` or `graph.stage == "physical"`.

## Workflow Data Flow

TRACE keeps the same stage order:

```text
ground -> logical -> physical
```

Logical flow:

```text
ground artifact
  -> logical.prepare
      creates graph(stage="logical") from grounded nodes
      initializes checkpoints and validator_script
  -> logical.builder
      asks the model for a StageArtifact containing graph/checkpoints/validator_script
      normalizes graph with tgraph.normalize_graph
  -> logical.validator
      calls tgraph.validate_graph with checkpoints and validator_script in context
  -> logical.repair
      uses tgraph inspect/patch/validate tools
```

Physical flow:

```text
logical_artifact
  -> physical.prepare
      copies logical_artifact.graph
      sets graph.stage = "physical"
      carries or derives checkpoints and validator_script as TRACE decides
  -> physical.builder
      enriches physical graph with image/flavor/addressing fields
  -> physical.validator
      validates graph structure and F4 intent/checkpoint/script context
  -> physical.repair
      uses the same tgraph operation surface
```

## TGraph Validation Boundary

TGraph validation has four layers:

```text
F1 format
F2 schema
F3 graph consistency
F4 checkpoint execution
```

F4 is a TGraph capability, not a TRACE-only capability. This avoids forcing every upper-layer agent or workflow to implement its own intent-checking executor.

F4 inputs are not stored inside the graph document. They are supplied to validation:

```python
validate_graph(
    graph,
    context=ValidationContext(
        preserve_topology_from=logical_graph,
        required_node_fields=["image", "flavor"],
        checkpoints=[...],
        validator_script="...",
        references={"logical": logical_graph},
    ),
)
```

TGraph F4 should support:

- batch checkpoints
- builtin generic assert functions
- custom validator script execution
- external registered checkpoint functions
- unified validation report output

TRACE remains responsible for generating checkpoints from user intent, knowledge bases, image catalogs, or workflow state. TGraph is responsible for executing those checkpoints against a graph.

## Builtin F4 Checkpoint Functions

TGraph should avoid a large list of overlapping domain-specific functions. The first builtin set should be six parameterized assert functions:

```text
assert_node
assert_port
assert_link
assert_path
assert_group
assert_graph
```

Design boundaries:

- `assert_node` checks node existence, type, fields, degree, and direct adjacency.
- `assert_port` checks port existence, IP/CIDR fields, and direct port or peer-node connection.
- `assert_link` checks direct links only.
- `assert_path` checks reachability, max hops, required nodes, and forbidden nodes.
- `assert_group` applies node/path/port checks across groups without introducing new domain concepts.
- `assert_graph` checks global graph assertions such as stage and topology preservation.

Examples:

```json
{
  "id": "cp_plc_exists",
  "func": "assert_node",
  "args": {
    "node": "PLC1",
    "exists": true,
    "type": "computer"
  }
}
```

```json
{
  "id": "cp_web_to_plc_via_fw",
  "func": "assert_path",
  "args": {
    "from": "WEB1",
    "to": "PLC1",
    "exists": true,
    "must_include": ["FW1"]
  }
}
```

```json
{
  "id": "cp_plc_lan_cidr",
  "func": "assert_port",
  "args": {
    "node": "PLC1",
    "cidr": "192.168.10.0/24"
  }
}
```

Domain-specific names such as `dmz_is_valid`, `industrial_cell_valid`, `iec62443_zone_valid`, `image_exists_in_catalog`, or `flavor_allowed_by_provider` should not be builtin TGraph functions. Upper layers can register them if needed.

## Validator Script SDK

Custom validator scripts need a stable read-only SDK so upper-layer agents can express rich intent without reimplementing graph algorithms.

Script entrypoint:

```python
def check_x(tgraph, **kwargs):
    ...
```

The `tgraph` argument should be a read-only `TGraphView`, not the mutable Pydantic model.

### Query API

```python
tgraph.node(node_id) -> dict | None
tgraph.nodes(type=None, ids=None, selector=None) -> list[dict]
tgraph.port(port_id) -> dict | None
tgraph.ports(node_id=None, cidr=None) -> list[dict]
tgraph.link(link_id) -> dict | None
tgraph.links(node_id=None, port_id=None, between=None) -> list[dict]
```

### Topology API

```python
tgraph.neighbors(node_id) -> list[str]
tgraph.degree(node_id) -> int
tgraph.connected(node_a, node_b) -> bool
tgraph.path_exists(source, target, max_hops=None) -> bool
tgraph.paths(source, target, max_hops=None, limit=20) -> list[list[str]]
```

### Path Helpers

```python
tgraph.all_paths_include(source, target, required_nodes) -> bool
tgraph.any_path_include(source, target, required_nodes) -> bool
tgraph.all_paths_exclude(source, target, forbidden_nodes) -> bool
tgraph.group_paths_include(sources, targets, required_nodes) -> bool
tgraph.group_isolated(sources, targets) -> bool
```

### CIDR-Centered Network Helpers

TGraph has ports with `ip` and `cidr`; it does not have explicit `segment` objects. The script SDK must not expose `segment_*` APIs.

Allowed helpers:

```python
tgraph.cidrs() -> list[str]
tgraph.ports_in_cidr(cidr) -> list[dict]
tgraph.nodes_in_cidr(cidr) -> list[dict]
tgraph.node_has_port_in_cidr(node_id, cidr, ip=None) -> bool
tgraph.switch_cidr(switch_id) -> str | None
tgraph.ports_share_cidr(port_ids=None, node_ids=None, cidr=None) -> bool
tgraph.ip_in_cidr(ip, cidr) -> bool
```

If an upper layer has concepts such as zone, subnet, segment, or cell, it must translate them into node ids, port ids, CIDRs, and path constraints before calling TGraph validation.

### Issue Builder

Scripts should use an issue helper instead of hand-writing report dictionaries:

```python
issue(
    code,
    message,
    severity="error",
    targets=None,
    location=None,
    details=None,
)
```

Example:

```python
def check_plc_lan(tgraph, **kwargs):
    if not tgraph.node_has_port_in_cidr("PLC1", "192.168.10.0/24"):
        return [issue("plc_not_on_lan", "PLC1 must have a LAN interface", targets=["PLC1"])]
    return []
```

### Script Safety

Validator scripts must be read-only and deterministic:

- no graph mutation
- no filesystem access
- no network access
- limited builtins
- limited modules such as `ipaddress` and `re`
- timeout protection
- exceptions converted to validation issues
- return type normalized from `list[ValidationIssue | dict]`

Catalog/domain knowledge can be passed via checkpoint args, validator kwargs, or external registered functions. TGraph should not fetch catalogs itself.

## TGraph Agent Capability Contract

TGraph should ship an agent-facing capability contract:

```text
src/tgraph/agent/playbooks/capabilities.md
```

Optionally, a structured schema can be added later:

```text
src/tgraph/agent/schemas/capabilities.schema.json
```

The capability contract explains:

- what TGraph can express directly
- what TGraph cannot express directly
- how agents should translate unsupported IaC requests into graph fields, checkpoints, validator scripts, or upper-layer catalog lookups

### Directly Expressible

TGraph can express:

- nodes
- ports
- links
- IPs
- CIDRs
- images
- flavors
- graph stage
- batch graph patch operations
- F1-F4 validation inputs
- canonical TGraph JSON
- target emission placeholders

### Not Directly Expressible

TGraph cannot directly:

- install software on a node
- execute shell/cloud-init/Ansible/package-manager operations
- query image catalogs
- guarantee an image exists
- guarantee a flavor exists for a provider
- represent firewall rules, IAM, routing tables, K8s manifests, zones, segments, packages, or arbitrary software fields
- know industrial-network, DMZ, compliance, or vendor-specific rules without upper-layer input

Unsupported graph fields such as `software`, `packages`, `zone`, `segment`, and `firewall_rules` must be rejected by schema and discouraged by prompt.

### Translation Examples

User request:

```text
Install OpenPLC on PLC1.
```

TGraph cannot install software. An upper-layer agent should query an image catalog for an image that already contains OpenPLC, then set `node.image` if a reliable image is found.

Graph patch:

```json
{
  "op": "ensure_node",
  "id": "PLC1",
  "type": "computer",
  "label": "PLC1",
  "image": {"id": "openplc", "name": "OpenPLC"}
}
```

User request:

```text
WEB must reach PLC only through FW1.
```

TGraph should express this as a path checkpoint:

```json
{
  "func": "assert_path",
  "args": {
    "from": "WEB1",
    "to": "PLC1",
    "exists": true,
    "must_include": ["FW1"]
  }
}
```

User request:

```text
WEB and PLC are in separate zones.
```

TGraph should not create a `zone` field. The upper layer must translate zones into concrete node groups and path/CIDR constraints, then pass those constraints to TGraph.

## Repair Tools

TRACE repair agents should use thin wrappers around standalone TGraph operations:

- inspect graph: `tgraph.inspect_graph`
- mutate graph: `tgraph.apply_patch`
- validate graph: `tgraph.validate_graph(..., context=ValidationContext(...))`
- mutate checkpoints: TRACE artifact-level `ensure_checkpoint` / `remove_checkpoint`
- mutate validator script: TRACE artifact-level `replace_validator_script`

There should be no transaction tools and no low-level one-operation mutation tools such as `add_node`, `add_link`, or `update_node`. The only graph write path is batch patch.

## Skill Scripts And CLI

There are three tool layers:

- `tgraph` CLI: operates on a bare TGraph graph document.
- TRACE skill scripts: operate on a TRACE stage artifact with `graph/checkpoints/validator_script`.
- `trace` CLI: operates on full workflow runs.

Skill scripts keep their names but change artifact semantics:

- `tgraph_inspect.py` reads `artifact["graph"]`.
- `tgraph_apply_patch.py` applies `graph_patch` with `tgraph.apply_patch`, then applies checkpoint and validator patches at the artifact layer.
- `tgraph_validate.py` calls `tgraph.validate_graph` with checkpoints and validator script in context.
- `tgraph_export.py --target tgraph-json` writes `artifact["graph"]`.

The `--stage logical|physical` option selects TRACE workflow stage semantics. It does not look up `tgraph_logical` or `tgraph_physical`.

## Module Migration

Delete or stop using the active compatibility layer:

- `src/trace/tools/tgraph/model.py`
- `src/trace/tools/tgraph/runtime.py`
- `src/trace/tools/tgraph/transaction.py`
- `src/trace/tools/tgraph/patch.py`
- `src/trace/tools/tgraph/export.py`
- `src/trace/tools/tgraph/protocol.py`
- `src/trace/tools/tgraph/validate/`

Move useful TRACE-owned logic:

- logical graph seed creation -> `src/trace/stages/logical/graph_seed.py`
- physical graph derivation -> `src/trace/stages/physical/graph_seed.py`
- prompt contract helpers -> stage prompt utilities that reference `src/tgraph/agent` docs

Prompt files should stop saying `TGraphJSON`, `profile`, `tgraph_logical`, or `tgraph_physical`.

## Testing Strategy

Migration should be test-led.

1. Add TGraph F4 tests for checkpoint models, builtin asserts, registry execution, script SDK, CIDR helpers, script exceptions, and report merging.
2. Change TRACE artifact schema tests to require `graph/checkpoints/validator_script`.
3. Change logical and physical stage tests to expect `artifact["graph"]`.
4. Change skill script tests to operate on the new stage artifact shape.
5. Delete old `tests/unit/tools/tgraph` compatibility tests or migrate them into `tests/unit/tgraph`.
6. Run integration/e2e tests.
7. Search for old names:

```text
TGraphJSON
TGraphRuntime
tgraph_logical
tgraph_physical
profile
trace.tools.tgraph
segment
software
packages
zone
```

Only historical design docs may keep old names.

## Acceptance Criteria

- TRACE workflow still runs `ground -> logical -> physical`.
- Logical and physical artifacts use `graph/checkpoints/validator_script`.
- Graph documents use only `stage`, `nodes`, and `links` at top level.
- Active source code does not import `trace.tools.tgraph.*`.
- `src/tgraph` is the only TGraph implementation.
- Graph mutation is batch patch only.
- TGraph F4 executes batch checkpoints and custom validator scripts.
- Validator scripts receive a read-only `TGraphView` SDK with CIDR-centered helpers.
- TGraph agent docs include a capability contract.
- `python -m pytest -q` passes.
