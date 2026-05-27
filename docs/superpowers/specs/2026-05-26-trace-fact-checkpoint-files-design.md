# TRACE Fact And Checkpoint Files Design

Status: draft for discussion, updated with resolved decisions

## Context

Logical and physical validation should stop depending on agent-authored JSON `func` / `args` checkpoints and free-form error messages. Ground already classifies intent into logical and physical facts, so downstream validation should align to that fact taxonomy and rely on TGraph APIs for stable checks and stable issue payloads.

The goal is not to make `statement` machine-parsed. The statement is an authoring hint for agents and a human-readable audit trail. Validators should use constraint ids, fact kinds, checkpoint function names, and TGraph check APIs.

New validation issues should not use a top-level `code` field or a top-level `kind` field. Stable classification should live in `details.issue_kind` and `details.fact_kind`, with `details.repair_target` used for repair routing. This is an intentional breaking change rather than a compatibility layer.

## Agreed Direction

Use files as the authoring and debugging surface:

```text
ground/logical_constraints.json
ground/physical_constraints.json
logical/checkpoints.py
physical/checkpoints.py
```

Constraints and checkpoints are both recorded as files. Agents can use normal file read/write/search/patch workflows, while deterministic validators enforce coverage, syntax, runtime behavior, and issue shape.

## Artifact Boundary

Stage artifacts should record file references instead of embedding constraint or checkpoint file contents. This keeps artifacts smaller and avoids spending tokens on files that an agent can read only when needed.

Example logical artifact shape:

```json
{
  "graph": "...",
  "constraint_files": {
    "logical": "ground/logical_constraints.json"
  },
  "checkpoint_files": {
    "logical": "logical/checkpoints.py"
  }
}
```

Example physical artifact shape:

```json
{
  "graph": "...",
  "constraint_files": {
    "physical": "ground/physical_constraints.json"
  },
  "checkpoint_files": {
    "physical": "physical/checkpoints.py"
  }
}
```

The run snapshot owns the referenced files. Resume/debug flows should preserve the files and references together.

Ground artifacts should keep `node_groups` embedded. Node inventory is small, frequently needed by logical prepare, and less noisy than constraints/checkpoints. Logical and physical constraints move to file references.

## Constraint Files

Logical constraints are stored in `ground/logical_constraints.json`:

```json
{
  "lc1": {
    "kind": "logical.addressing.subnet",
    "statement": "SW_DMZ represents subnet 10.10.10.0/24."
  },
  "lc9": {
    "kind": "logical.topology.chain",
    "statement": "explicit chain WEB -> SW_DMZ -> R_CORE."
  }
}
```

Physical constraints are stored in `ground/physical_constraints.json`:

```json
{
  "pc1": {
    "kind": "physical.image.capability",
    "statement": "FIREWALL requires firewall appliance capability."
  }
}
```

Rules:

- The JSON object key is the constraint id.
- Constraint objects contain `kind` and `statement`.
- No `version` field for now.
- `statement` is readable context for agents and humans.
- Validators do not parse `statement`.
- `kind` is the machine-facing fact category.
- Constraint file writers and validators must prevent duplicate keys. A duplicate constraint id should become a deterministic constraint-file validation issue, not be silently overwritten by JSON parsing.

## Checkpoint Files

Each stage owns one checkpoint Python file:

```text
logical/checkpoints.py
physical/checkpoints.py
```

Each constraint must have exactly one checkpoint function named `check_<constraint_id>`:

```python
def check_lc9(tgraph):
    return tgraph.check_chain(["WEB", "SW_DMZ", "R_CORE"])
```

For physical constraints:

```python
def check_pc1(tgraph):
    return tgraph.check_image_capability("FIREWALL", "firewall_appliance")
```

Rules:

- Checkpoint files are regenerable derived artifacts.
- Author or repair agents may rewrite them in batch.
- Normal facts should prefer one-line calls to TGraph `check_*` APIs.
- One-line TGraph API calls are recommended, not required. Validators may warn or provide repair guidance for unnecessarily complex normal checkpoints, but should not fail valid checkpoint functions solely because they use helper logic.
- `logical.custom` and `physical.custom` can use custom Python logic.
- Custom logic should still return issues through TGraph issue helpers or TGraph check APIs.
- Function naming maps checkpoints to constraints; the function name supplies the constraint id.

## Imports

Checkpoint files may use imports, but imports should be allowlisted and sandboxed.

Allowed imports should be limited to pure standard-library helpers such as:

```python
import math
import re
import ipaddress
from itertools import combinations
```

Disallowed imports should include filesystem, process, network, dynamic loading, and provider SDK access, such as:

```python
import os
import subprocess
import socket
import requests
import pathlib
import importlib
```

Validators should statically inspect imports and report checkpoint issues instead of crashing.

Sandbox policy:

- Parse checkpoint files with AST before execution.
- Allow only explicit import allowlist entries.
- Execute checkpoint code in isolated subprocesses with a configurable maximum process concurrency.
- Default process concurrency: `checkpoint_max_processes = 4`.
- The initial runner executes one subprocess per checkpoint file. Future runners may move to one subprocess per checkpoint function if stronger isolation becomes necessary, but either mode must obey the configured process limit.
- Enforce a short timeout per checkpoint function or per checkpoint file.
- Default timeout: `checkpoint_timeout_seconds = 5`.
- Provide a restricted `__builtins__` set, for example `len`, `range`, `enumerate`, `sorted`, `min`, `max`, `sum`, `any`, `all`, `set`, `list`, `dict`, `tuple`, `str`, `int`, `float`, `bool`, `abs`, `round`, `zip`, and basic exception types.
- Remove side-effect builtins such as `open`, `eval`, `exec`, `compile`, `input`, `globals`, `locals`, and `vars`.
- Provide a guarded `__import__` implementation that permits only the static import allowlist. This keeps allowed imports working while still blocking arbitrary module access.
- Compile with the real checkpoint file path as the Python filename so traceback line numbers map back to `checkpoints.py`.
- Convert syntax errors, disallowed imports, runtime exceptions, timeouts, and invalid return values into checkpoint/runtime validation issues.

## Fact Kind Taxonomy

Logical fact kinds:

```text
logical.addressing.subnet
logical.addressing.interface
logical.topology.direct
logical.topology.chain
logical.topology.ring
logical.topology.star
logical.topology.mesh
logical.custom
```

Notes:

- `logical.topology.mesh` means full mesh: every node in the set directly connects to every other node.
- `dual_homed` is not a separate kind; it can be represented as star, chain, or direct links.
- `hub_spoke` is not a separate kind for now; use star.
- `hierarchy` is not a separate kind for now; decompose into direct/chain/star/mesh where possible, otherwise use `logical.custom`.

Physical fact kinds:

```text
physical.image.capability
physical.image.exact
physical.flavor.minimum
physical.flavor.exact
physical.custom
```

Notes:

- `exact` kinds are only for user-specified concrete image or flavor requirements.
- `physical.image.exact` compares image `id`.
- `physical.flavor.exact` compares the normalized flavor object, currently `{vcpu, ram, disk}`.
- Agents must not invent exact image or flavor facts.
- Unknown or experimental facts should not create arbitrary new kind namespaces. Use `logical.custom` or `physical.custom`.

## TGraph Check API Direction

Each formal fact kind should have a corresponding stable TGraph check API. The API should use simple Pythonic method names such as `tgraph.check_chain(...)`, while the mapping table keeps the API aligned to fact kinds.

Rejected shapes:

```python
tgraph.check.logical.topology.chain(["WEB", "SW_DMZ", "R_CORE"])
tgraph.check_fact("logical.topology.chain", nodes=["WEB", "SW_DMZ", "R_CORE"])
tgraph.logical_topology.check_chain(["WEB", "SW_DMZ", "R_CORE"])
```

The nested shapes are valid Python but look like a custom DSL. The string-based `check_fact(...)` shape aligns perfectly with kind names but is weaker for discoverability and static feedback.

Accepted conceptual mapping:

```text
logical.addressing.subnet    -> tgraph.check_subnet(...)
logical.addressing.interface -> tgraph.check_interface(...)
logical.topology.direct      -> tgraph.check_direct_link(..., link_key=None)
logical.topology.chain       -> tgraph.check_chain(..., link_keys=None)
logical.topology.ring        -> tgraph.check_ring(..., link_keys=None)
logical.topology.star        -> tgraph.check_star(..., link_keys=None)
logical.topology.mesh        -> tgraph.check_mesh(..., link_keys=None)

physical.image.capability    -> first design uses agent-authored checkpoint logic based on static docs
physical.image.exact         -> tgraph.check_image_exact(...)
physical.flavor.minimum      -> tgraph.check_flavor_minimum(...)
physical.flavor.exact        -> tgraph.check_flavor_exact(...)
```

TGraph check APIs should generate stable, targeted `message`, `location`, and `details`. Agents should not hand-author normal validation error text for formal fact kinds.

For formal fact kinds such as chain, ring, star, mesh, subnet, image, and flavor, each TGraph `check_*` API should predefine the likely failure cases and return targeted repair-friendly messages and details. Repair agents should be able to understand the issue from the message and structured details without consulting a separate issue-kind library.

`details.issue_kind` may still be emitted for grouping/debugging, but it is not the primary agent-facing contract. `details.fact_kind`, `details.constraint_id`, `details.checkpoint_function`, `details.repair_target`, and targeted fields such as `expected_edge`, `missing_node`, `expected_cidr`, or `actual_value` are more important.

For `logical.custom` and `physical.custom`, TRACE should provide guidance for writing good custom issue messages and details, but the checkpoint author may define the specific failure messages.

For `physical.image.capability`, the first design trusts the physical-stage author to read the static image/flavor knowledge and write the appropriate checkpoint. TGraph does not need a built-in capability catalog in the first version. A deterministic catalog-backed `check_image_capability` can be added later if needed.

Accepted custom checkpoint example:

```python
def check_lc_custom1(tgraph):
    paths = tgraph.paths("PLC1", "INTERNET", limit=3)
    if not paths:
        return []

    return tgraph.issue(
        message="PLC1 must not have any path to INTERNET.",
        repair_target="graph",
        targets=["PLC1", "INTERNET"],
        details={
            "expected": "no path from PLC1 to INTERNET",
            "actual_paths": paths,
        },
    )
```

## Validator Issue Taxonomy

Validation issues use two layers:

1. Fact validation issues: checkpoint ran successfully, but the graph or metadata does not satisfy the fact.
2. Checkpoint/runtime issues: checkpoint or constraint files are malformed, incomplete, unsafe, or failed at runtime.

Checkpoint/runtime issue kinds, stored as `details.issue_kind`:

```text
constraint.file.missing
constraint.file.invalid_json
constraint.shape.invalid
constraint.kind.unknown

checkpoint.coverage.missing
checkpoint.coverage.orphan
checkpoint.coverage.duplicate
checkpoint.syntax.invalid
checkpoint.import.disallowed
checkpoint.api.unknown
checkpoint.execution.exception
checkpoint.execution.timeout
checkpoint.return.invalid

validator.internal_error
```

Example checkpoint runtime issue:

```json
{
  "message": "check_lc9 failed with NameError: name 'check_chainn' is not defined",
  "location": "logical/checkpoints.py:12",
  "details": {
    "issue_kind": "checkpoint.execution.exception",
    "constraint_id": "lc9",
    "fact_kind": "logical.topology.chain",
    "statement": "explicit chain WEB -> SW_DMZ -> R_CORE.",
    "checkpoint_function": "check_lc9",
    "checkpoint_path": "logical/checkpoints.py",
    "repair_target": "checkpoint"
  }
}
```

Example checkpoint file timeout issue:

```json
{
  "message": "logical/checkpoints.py exceeded the checkpoint timeout of 5 seconds.",
  "location": "logical/checkpoints.py",
  "details": {
    "issue_kind": "checkpoint.execution.timeout",
    "checkpoint_path": "logical/checkpoints.py",
    "repair_target": "checkpoint",
    "timeout_seconds": 5,
    "scope": "file"
  }
}
```

The first runner executes one subprocess per checkpoint file, so a dead loop inside one function may be reported at file scope. This is acceptable for the first version as long as the issue message is clear.

Example fact validation issue:

```json
{
  "message": "logical chain is missing direct edge WEB -- SW_DMZ",
  "details": {
    "issue_kind": "logical.topology.chain.missing_edge",
    "constraint_id": "lc9",
    "fact_kind": "logical.topology.chain",
    "checkpoint_function": "check_lc9",
    "repair_target": "graph",
    "expected_edge": ["WEB", "SW_DMZ"],
    "targets": ["WEB", "SW_DMZ"]
  }
}
```

## Repair Routing

Validators should provide `details.repair_target` so repair agents do not need to infer the fix surface from long natural-language messages.

Suggested targets:

```text
checkpoint -> rewrite or patch checkpoints.py
constraint -> rewrite or patch logical_constraints.json / physical_constraints.json
graph      -> patch logical topology, ports, IPs, CIDRs
metadata   -> patch physical image or flavor metadata
internal   -> validator/runtime bug, not normally agent-fixable
```

Default routing:

- `details.issue_kind=checkpoint.*` issues route to `checkpoint`.
- `details.issue_kind=constraint.*` issues route to `constraint`.
- `details.fact_kind=logical.topology.*` fact failures route to `graph`.
- `details.fact_kind=logical.addressing.*` fact failures route to `graph`.
- `details.fact_kind=physical.image.*` fact failures route to `metadata`.
- `details.fact_kind=physical.flavor.*` fact failures route to `metadata`.

Repair agents may read constraint files by default but should not modify them by default. Constraint edits should require an explicit `details.repair_target="constraint"` issue or a separate human-approved path.

## Agent Tools Direction

Prefer standard file-oriented tools because agents are likely strongest at read/search/write/patch workflows.

Useful generic tools:

```text
list_files
read_file
write_file
apply_patch
search_files
```

The tools should be scoped to the current run/stage workspace.

Still keep deterministic stage tools:

```text
validate_constraints_file
validate_checkpoints_file
inspect_graph
validate_mutation_file
execute_mutation_file
validate_stage
```

File tools provide the authoring surface. Deterministic tools provide safety, validation, and controlled mutation execution. Repair agents mutate graphs by writing mutation files; they should not use a legacy whole-graph patch helper as the primary repair path.

## Agent Support Documentation

Core agent-facing docs should live inside the TGraph package so runtime prompts and tool descriptions can load them directly:

```text
src/tgraph/agent/docs/index.md
src/tgraph/agent/docs/tgraph_view_api.md
src/tgraph/agent/docs/tgraph_check_api.md
src/tgraph/agent/docs/tgraph_editor_api.md
src/tgraph/agent/docs/fact_kinds.md
src/tgraph/agent/docs/checkpoint_authoring.md
src/tgraph/agent/docs/mutation_authoring.md
src/tgraph/agent/docs/repair_playbook.md
```

`index.md` is the directory and routing page. It should tell agents which short doc to read for each task:

```text
- Reading/inspecting graphs -> tgraph_view_api.md
- Writing checkpoint files -> checkpoint_authoring.md + tgraph_check_api.md + fact_kinds.md
- Writing mutation files -> mutation_authoring.md + tgraph_editor_api.md
- Repairing from validation issues -> repair_playbook.md
```

README and architecture docs should link to these package docs instead of duplicating the content. The package docs should stay short, example-heavy, and searchable.

Trace image/flavor knowledge should stay simple for now. It can be represented as searchable static docs or data files that agents read with the same standard file/search tools. Do not introduce a complex image/flavor query tool or catalog service in the first design. Deterministic catalog validation can be added later if needed.

## Mutation Scripts

Repair agents should mutate TGraph through controlled mutation scripts rather than directly editing the full graph JSON.

Mutation scripts are per-attempt files:

```text
logical/mutations/attempt_3.py
physical/mutations/attempt_2.py
```

Each script defines:

```python
def mutate(tgraph):
    tgraph.ensure_direct_link("WEB", "SW_DMZ")
    tgraph.ensure_direct_link("SW_DMZ", "R_CORE")
    return tgraph
```

Physical mutation example:

```python
def mutate(tgraph):
    tgraph.set_node_image("FIREWALL", {"id": "vyos-fw", "name": "VyOS firewall"})
    tgraph.set_node_flavor("FIREWALL", {"vcpu": 2, "ram": 2048, "disk": 10})
    return tgraph
```

Mutation scripts operate on a controlled `TGraphEditor`, not the raw graph dict. Checkpoints receive a read-only `TGraphView`; mutation scripts receive a write-capable editor.

Mutation scripts use the same basic safety model as checkpoint files: AST preflight, import allowlist, guarded imports, restricted builtins, subprocess isolation, timeout, and conversion of execution failures into validation issues. The execution object is different: checkpoints receive read-only `TGraphView`, while mutations receive `TGraphEditor`.

Execution is transactional:

1. Repair agent receives validation issues.
2. Repair agent reads relevant constraints, checkpoints, and graph context.
3. Repair agent writes a mutation script for the current attempt.
4. Runtime executes `mutate(tgraph)` against a graph copy.
5. Runtime validates schema, stage invariants, and checkpoints.
6. The mutated graph is committed only if execution and validation succeed.
7. On failure, the original graph remains unchanged and the repair agent receives mutation/runtime/validation issues.

Initial mutation APIs should be idempotent where possible:

```text
tgraph.ensure_node(...)
tgraph.ensure_port(...)
tgraph.ensure_direct_link(...)
tgraph.ensure_chain(...)
tgraph.ensure_ring(...)
tgraph.ensure_star(...)
tgraph.ensure_mesh(...)
tgraph.remove_direct_link(...)
tgraph.remove_links_between(...)
tgraph.remove_chain(...)
tgraph.remove_ring(...)
tgraph.remove_star(...)
tgraph.remove_mesh(...)
tgraph.ensure_subnet(...)
tgraph.ensure_interface(...)
tgraph.set_node_image(...)
tgraph.set_node_flavor(...)
```

Agents should not directly mutate `nodes`, `ports`, `links`, or raw dict/list internals. Direct whole-graph rewrites are outside the preferred repair path.

Per-attempt mutation files are kept for debugging. Final artifacts may reference the last successful mutation or keep only the repair history, but the graph remains the source of final state.

## TGraph Initialization

TGraph should provide initialization helpers, but catalog and defaulting policy should remain caller-owned by Trace.

Logical initialization:

```python
tgraph.init_logical_skeleton(node_groups)
```

Behavior:

- Expands `node_groups` into nodes.
- Sets `stage="logical"`.
- Initializes `label` from node id.
- Initializes empty `ports` and `links`.
- Does not infer topology, ports, CIDRs, IPs, image, or flavor.

Logical skeleton should be node-only. Inferring topology from constraints during skeleton init would make constraints too strict and reduce flexibility. Logical author/repair should add topology and addressing through mutation APIs.

Physical initialization:

```python
tgraph.init_physical_skeleton(
    logical_graph,
    defaults_by_node_type={
        "computer": {"image": ..., "flavor": ...},
        "router": {"image": ..., "flavor": ...},
        "switch": {"image": ..., "flavor": ...},
    },
)
```

Behavior:

- Copies logical nodes, ports, and links.
- Sets `stage="physical"`.
- Applies default image/flavor by node type.
- Does not overwrite existing non-empty image/flavor values.
- Lets physical author/repair later update special nodes according to physical constraints and catalog results.

Current TGraph node schema allows optional `image` and `flavor` on every node type. It does not require switch/router/computer nodes to have deployment metadata. Therefore default image/flavor requirements are Trace physical policy, not intrinsic TGraph schema rules.

Trace should support node-type defaults, and those defaults may be `null` for node types that are treated as abstract infrastructure in a scenario:

```json
{
  "computer": {
    "image": {"id": "img_linux_default", "name": "linux-default"},
    "flavor": {"vcpu": 1, "ram": 1024, "disk": 10}
  },
  "router": {
    "image": {"id": "img_router_default", "name": "router-default"},
    "flavor": {"vcpu": 1, "ram": 512, "disk": 4}
  },
  "switch": {
    "image": null,
    "flavor": null
  }
}
```

Physical validation should not blindly require image/flavor for all nodes unless the selected Trace policy says every physical node is deployable. Required deployment metadata should be derived from:

- node-type default policy,
- physical constraints,
- image/flavor exact or capability facts,
- and any explicit deployment policy selected by the caller.

### TGraph Editor API Semantics

Logical mutation APIs:

```python
tgraph.ensure_node("R_CORE", type="router", label="R_CORE")
tgraph.remove_node("TEMP1")

tgraph.ensure_port("R_CORE", port_id="R_CORE__SW_DMZ", cidr="10.10.10.0/24", ip="10.10.10.1")
tgraph.ensure_subnet("SW_DMZ", cidr="10.10.10.0/24")
tgraph.ensure_interface("R_CORE", segment="SW_DMZ", ip="10.10.10.1/24")

tgraph.ensure_direct_link("WEB", "SW_DMZ", link_key=None)
tgraph.ensure_chain(["WEB", "SW_DMZ", "R_CORE"], link_keys=None)
tgraph.ensure_ring(["R1", "R2", "R3", "R1"], link_keys=None)
tgraph.ensure_star(center="SW_CORE", leaves=["PC1", "PC2", "PC3"], link_keys=None)
tgraph.ensure_mesh(["R1", "R2", "R3"], link_keys=None)
tgraph.remove_direct_link("WEB", "INTERNET", link_key=None)
tgraph.remove_links_between("WEB", "INTERNET")
tgraph.remove_chain(["WEB", "SW_DMZ", "R_CORE"], link_keys=None)
```

Physical mutation APIs:

```python
tgraph.set_node_image("FIREWALL", {"id": "vyos-fw", "name": "VyOS firewall"})
tgraph.set_node_flavor("WEB", {"vcpu": 2, "ram": 4096, "disk": 20})
tgraph.ensure_default_image(default_image)
tgraph.ensure_default_flavor(default_flavor)
```

Common defaults:

```python
overwrite = False
create_missing_nodes = False
```

`ensure_direct_link` should automatically find or create link ports, generate stable port/link ids, avoid duplicate links, and preserve existing non-empty IP/CIDR values unless overwrite is explicit.

`ensure_interface(node, segment, ip)` should ensure the node is directly linked to the segment switch, assign the node-side interface address, and set the target CIDR on both the node-side port and switch-side port.

`ensure_subnet(switch, cidr)` should not create a synthetic marker port. Instead, the subnet is represented by the switch ports themselves: all ports on the switch should use the target CIDR. `check_subnet` should validate the same invariant. This avoids relying on an artificial marker port that may be hard for agents or users to reason about.

Mutation APIs may return operation results for debugging, such as:

```python
{"changed": true, "link_id": "...", "ports": ["...", "..."]}
```

Agents are not required to consume these return values.

### Port And Link Identity

Port and link ids are generated by `TGraphEditor`; agents should not hand-author ids unless an advanced API explicitly asks for one.

There is no required `l__` prefix for links. Link ids already live in the `links` collection, so the prefix adds noise without much value.

Default direct link between two nodes:

```python
tgraph.ensure_direct_link("WEB", "SW_DMZ")
```

Generated ids:

```text
link id: SW_DMZ-WEB-1
port ids:
  on WEB:    _SW_DMZ-1
  on SW_DMZ: _WEB-1
```

Port ids are node-local and should start with `_`, followed by the peer node id, `-`, and a numeric key. The key increments per owner/peer pair.

This requires links to identify endpoints by `(node_id, port_id)`, not by globally unique `port_id` alone. In emitted TGraph JSON, `from_node` and `to_node` should be populated and treated as endpoint identity fields. Validators and views should not assume port ids are globally unique.

There is no need to preserve a global-unique-port-id assumption for the current scenario. Port ids are node-local by design.

The default link id uses a canonical sorted node pair plus the pair key so `ensure_direct_link("WEB", "SW_DMZ")` and `ensure_direct_link("SW_DMZ", "WEB")` are idempotent.

Multiple links between the same two nodes must be supported. Additional parallel links require an explicit `link_key` so ids stay stable and intentional:

```python
tgraph.ensure_direct_link("R1", "R2", link_key="wan_primary")
tgraph.ensure_direct_link("R1", "R2", link_key="wan_backup")
```

Generated ids:

```text
R1-R2-wan_primary
on R1: _R2-1
on R2: _R1-1

R1-R2-wan_backup
on R1: _R2-2
on R2: _R1-2
```

Rules:

- `link_key` is an explicit semantic identity for a parallel link, such as `wan_primary` or `wan_backup`.
- A call without `link_key` refers to the default link for that node pair.
- A call with `link_key` refers to a specific parallel link for that node pair.
- Port numeric keys are allocated by the editor and increment per owner/peer pair.
- Link ids use the explicit `link_key` when provided. Without `link_key`, the default link id uses the canonical pair key, for example `SW_DMZ-WEB-1`.
- Repeated `ensure_direct_link(A, B, link_key="...")` calls must find the existing semantic link by link id and must not allocate new ports.
- Formal topology checks such as chain/star/ring/mesh should treat any direct link between two nodes as satisfying adjacency unless the checkpoint explicitly checks a `link_key`.
- `check_direct_link(A, B, link_key=None)` checks the default/any direct link by default, and checks the specific semantic link when `link_key` is provided.
- Shape checks may accept `link_keys` for advanced cases:
  - chain/ring: list of link keys aligned to adjacent pairs
  - star: dict from leaf node id to link key
  - mesh: dict keyed by canonical pair string or tuple
  If `link_keys` is omitted, any direct link satisfies each adjacency.
- The link object remains the source of truth for endpoints. Link ids are stable identifiers, not the only way to recover topology.
- Canonical `node_id` grammar for the first design: `^[A-Z][A-Z0-9_]*$`.
- `link_key` grammar for the first design: `^[A-Za-z][A-Za-z0-9_]*$`.
- Generated `port_id` grammar: `^_[A-Z][A-Z0-9_]*-[0-9]+$`.
- Canonical node ids and link keys must not contain `-` because link ids use `-` as the delimiter between node ids and keys, and port ids use `-` between peer node id and numeric key. The ground stage should generate `SW_DMZ`, not `SW-DMZ`.
- If future ids need broader character support, the editor must add escaping deliberately rather than silently accepting ambiguous ids.

### Remove Semantics

Removal APIs must be explicit about cascade behavior.

`remove_direct_link(a, b, link_key=None)`:

- Removes exactly one link: the default link when `link_key` is omitted, or the semantic parallel link when `link_key` is provided.
- Removes the two endpoint ports used only by that link.
- Does not remove nodes.
- Does not remove other parallel links between the same nodes.
- If no matching link exists, it is idempotent and returns `changed=false`.

`remove_links_between(a, b)`:

- Removes all links between the two nodes, including default and semantic parallel links.
- Removes endpoint ports used only by those links.
- Does not remove nodes.
- Should be used only when the repair intent is to remove all adjacency between two nodes.
- Because this can remove multiple links and their IP/CIDR-bearing ports, validation/mutation feedback should mark it as destructive and list the affected link/port ids.

`remove_chain(nodes, link_keys=None)`, `remove_ring(...)`, `remove_star(...)`, and `remove_mesh(...)`:

- Remove the direct links implied by the shape.
- Without `link_keys`, remove only the default link for each adjacent pair.
- With `link_keys`, remove the specified semantic links.
- Do not remove nodes.
- Do not remove unrelated parallel links.

`remove_node(node_id, remove_incident_links=True)`:

- If `remove_incident_links=True`, removes all incident links, removes the node, and removes the peer endpoint ports that belonged only to those incident links.
- If `remove_incident_links=False`, fails with a controlled mutation issue when incident links exist.
- Removing a node always removes all ports on that node.

`remove_port(node_id, port_id)` should be an advanced operation only:

- If the port is linked, the operation should fail unless the caller explicitly requests link removal too.
- Prefer removing links or interfaces rather than deleting ports directly.

When a removal deletes a port with IP/CIDR data, that address information is intentionally removed. The operation result should include the removed link ids and removed port ids so repair history remains inspectable.

## Open Design Questions

None at the current design level. Remaining choices can be handled during implementation planning.

## Resolved Decisions

- Constraint files are `ground/logical_constraints.json` and `ground/physical_constraints.json`.
- Constraint files are JSON objects keyed by constraint id.
- Constraint file writers/validators must detect duplicate keys instead of silently accepting last-write-wins JSON parsing.
- Ground artifacts keep `node_groups` embedded; node inventory is not moved to a file in the first design.
- Checkpoint files are `logical/checkpoints.py` and `physical/checkpoints.py`.
- Normal checkpoint functions should prefer one-line TGraph check API calls, but this is a recommendation rather than a hard validation requirement.
- Artifacts record file references instead of embedding file contents.
- Repair agents cannot modify constraint files by default.
- Issue classification lives in `details.issue_kind` and `details.fact_kind`, not top-level `kind`.
- New validation issues do not use top-level `code`; this is a breaking change, not a compatibility layer.
- `physical.image.exact` compares image `id`; `physical.flavor.exact` compares normalized flavor fields `{vcpu, ram, disk}`.
- Checkpoint files may import allowlisted modules.
- Checkpoints are parsed with AST, import-allowlisted, executed in isolated subprocesses with a configurable process concurrency limit, run with restricted builtins, compiled with the real checkpoint file path for traceback line mapping, and converted to checkpoint/runtime issues on syntax/import/runtime/timeout/return-shape failures.
- Mutation scripts follow the same sandbox model as checkpoint files, but receive a controlled `TGraphEditor` instead of a read-only `TGraphView`.
- Default checkpoint subprocess concurrency is 4; default checkpoint timeout is 5 seconds.
- The initial checkpoint runner executes one subprocess per checkpoint file.
- Formal TGraph `check_*` APIs should return targeted, repair-friendly messages and details for known failure cases. `details.issue_kind` is optional grouping/debug metadata, not the primary repair-agent contract.
- Formal check APIs use simple Pythonic method names such as `tgraph.check_chain(...)`, `tgraph.check_subnet(...)`, and `tgraph.check_image_capability(...)`; fact-kind alignment is documented in the mapping table and injected into issue details by the runner.
- Custom checkpoint authors receive guidance for issue messages/details, but custom issue semantics are authored with the custom check.
- Core agent-facing docs live in `src/tgraph/agent/docs/`, with `index.md` as the routing/directory page. README and architecture docs should link to these package docs.
- Trace image/flavor knowledge remains simple searchable static documentation/data for now; no dedicated catalog query service is required in the first design.
- `physical.image.capability` trusts the physical-stage author to read static image/flavor knowledge and write the appropriate checkpoint in the first version; TGraph does not include a built-in capability catalog yet.
- Repair agents mutate graphs by writing per-attempt mutation scripts that call controlled TGraph editor APIs. Runtime executes them transactionally against a graph copy and commits only after validation succeeds.
- Logical skeleton initialization expands `node_groups` into nodes only. It does not infer topology or addressing.
- Physical skeleton initialization copies logical topology, applies node-type default image/flavor policy, and lets physical author/repair modify special nodes afterward.
- Image/flavor defaults are Trace policy inputs, not hard-coded TGraph catalog knowledge. Switch/router image/flavor may be null when the selected policy treats them as abstract infrastructure.
- `ensure_subnet` / `check_subnet` operate over the switch's real ports. A subnet fact means the switch's ports use the target CIDR; TGraph should not create a synthetic subnet marker port.
- `ensure_interface` sets the target CIDR on both node-side and switch-side ports.
- Link keys are part of both mutation and check API semantics. Direct/shape checks accept optional `link_key` / `link_keys`, while default topology checks treat any direct link between two nodes as satisfying adjacency.
- Port ids are node-local. The system should not preserve the old assumption that port ids are globally unique.
- First-design id grammar: `node_id=^[A-Z][A-Z0-9_]*$`, `link_key=^[A-Za-z][A-Za-z0-9_]*$`, generated `port_id=^_[A-Z][A-Z0-9_]*-[0-9]+$`; node ids and link keys must not contain `-`.
- File-scope checkpoint timeout is acceptable for the first runner, but the timeout issue must clearly name the file, timeout, and repair target.
- Remove APIs delete the targeted links and the endpoint ports used only by those links, but do not delete nodes unless `remove_node` is called explicitly.
- `remove_links_between` is destructive and should report affected links/ports so repair agents do not use it casually.
- Migration from current `constraint_scripts`, `checkpoints`, and `validator_script` should be a one-shot replacement, not a compatibility layer.
