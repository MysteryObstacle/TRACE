# TGraph Contract

This document is the authoritative prompt-facing reference for TGraph semantics in TRACE.
If a stage prompt and this contract disagree, follow this contract.

## Canonical TGraphJSON shape

- Top-level keys: `profile`, `nodes`, `links`
- Logical profile: `logical.v1`
- Physical profile: `taal.default.v1`

### Node object

- Required keys: `id`, `type`, `label`, `ports`
- Optional keys: `image`, `flavor`
- Supported `type` values: `switch`, `router`, `computer`
- `image` must be an object with `id` and `name` when present.
- `flavor` must be an object with `vcpu`, `ram`, and `disk` when present.
- Do not emit string shorthand for `image` or `flavor`.

### Port object

- Required key: `id`
- Prompt-visible semantic keys: `ip`, `cidr`

### Link object

- Required keys: `id`, `from_port`, `to_port`
- Optional keys: `from_node`, `to_node`
- Canonical link id format after normalization: `{from_port}--{to_port}`
- Do not invent alternate link shapes such as `source/target`, `a/b`, nested endpoint objects, or `connected`

## Validator layers

- F1: top-level format checks
- F2: schema/profile checks
- F3: structural and addressing consistency checks
- F4: authored stage-specific intent checks against the current graph

## Key logical-stage validator expectations

- Each port can participate in at most one link
- Switch ports:
  - `ip` should be empty
  - `cidr` must be non-empty
  - all switch ports on the same switch should share the same CIDR
- Router ports:
  - `ip` must be non-empty
- If a port has both `ip` and `cidr`, the IP must belong to the CIDR
- Builder and repair should preserve a graph that remains compatible with F1-F4 for the active stage
- F3 checks implementation-complete graph validity, not whether an address was explicitly requested by intent.
- Implementation defaults are graph-validity choices, not intent facts.
- Explicit Interface/Subnet facts should be validated by F4 exact checks; builder-created default IP/CIDR values may satisfy F3 without becoming new GroundArtifact constraints.

## F4 checkpoint SDK

- The same checkpoint payload shape is used in both logical and physical stages.
- Logical stage uses `logical_checkpoints` and optional `logical_validator_script`.
- Physical stage uses `physical_checkpoints` and optional `physical_validator_script`.

### F4 checkpoint execution model

- F4 executes authored checkpoints, not validator scripts directly.
- Each checkpoint must name exactly one function in `func`.
- The named function is resolved first from the built-in checkpoint SDK, then from public functions defined in the stage validator script.
- A custom validator function runs only when a checkpoint `func` names that function.
- A standalone function such as `logical_validator` or `physical_validator` is not an automatic entry point.
- The validator script is a function library for checkpoints; it is not itself a scheduled check.
- `constraint_ids` are provenance and coverage metadata; they do not change what a checkpoint function checks.
- Attach a constraint id to the checkpoint whose function actually validates that constraint's semantics.
- When `logical_constraints` or `physical_constraints` are supplied, F4 reports authored checkpoints that omit a required constraint id or reference an unknown constraint id.

### Built-in checkpoint functions

1. `connect_nodes(node_a: str, node_b: str)`
   - passes when `node_a` and `node_b` are directly adjacent
2. `switch_has_subnet(switch_id: str, expected_cidr: str)`
   - passes when `switch_id` is a switch and all of its ports carry exactly `expected_cidr` with empty `ip`
   - use this for `Subnet fact: <SWITCH_ID> represents subnet <CIDR>.`
3. `node_interface_on_segment(node_id: str, segment_id: str, expected_ip: str, expected_cidr: str)`
   - passes when `node_id` is directly attached to switch `segment_id` and the node-side port has exactly `expected_ip` and `expected_cidr`
   - use this for `Interface fact: <NODE_ID> uses IP <IP>/<PREFIX> on segment <SWITCH_ID>.`
4. `path_exists(source_id: str, target_id: str)`
   - passes when at least one path exists between source and target
5. `path_must_include(source_id: str, target_id: str, via: str)`
   - passes when at least one source-to-target path includes `via`

### Safe checkpoint authoring patterns

- Prefer pairwise structural checks over fragile global scripts
- For an explicit chain like `A -> B -> C`, emit pairwise `connect_nodes` checkpoints
- Use `connect_nodes` for graph adjacency and expanded topology shapes.
- Use `switch_has_subnet` for concrete switch-carried subnet constraints.
- Use `node_interface_on_segment` for concrete fixed interface IP/CIDR constraints on a switch segment.
- Use custom validator scripts only for authored constraints that are not covered by built-in functions.
- If a constraint is already effectively enforced by F1-F3 or by another safer checkpoint, attach its `constraint_id` to the nearest supporting checkpoint instead of writing a fragile custom script

## Custom validator script surface

- Custom functions must use the signature: `def your_check(tgraph, **kwargs):`
- Custom functions must return `list[dict]`
- Return `[]` when the check passes

### Issue dict shape

- `code`: `str`
- `message`: `str`
- `severity`: `error` or `warning`
- `targets`: `list[str]`
- `json_paths`: `list[str]`
- Validation output additionally includes `provenance`
- Do not emit legacy `scope`

### Validation provenance shape

- `provenance.layer`: `f1`, `f2`, `f3`, or `f4`
- `provenance.source`: `builtin` or `authored_check`
- `provenance.check_id`: optional authored-check id
- `provenance.constraint_ids`: optional list of grounded constraint ids
- `provenance.func`: optional check function name
- `provenance.impl_source`: optional `sdk`, `custom`, or `unknown`
- `provenance.args`: optional concrete check args captured at execution time
- `provenance.artifact`: optional authored artifact name, for example `logical_validator_script`

### `tgraph` helper surface for custom script

- `tgraph.get_node(node_id)` -> `dict | None`
- `tgraph.get_nodes(node_ids=None)` -> `list[dict]`
  - when `node_ids` is omitted, returns all nodes
  - when `node_ids` is supplied, returns nodes in the requested order, omitting unknown ids
- `tgraph.get_link(link_id)` -> `dict | None`
- `tgraph.list_links(node_id=None, port_id=None)` -> `list[dict]`
- `tgraph.get_links(link_ids=None, node_id=None, port_id=None)` -> `list[dict]`
  - when `link_ids` is supplied, returns links in the requested order
  - otherwise filters by optional `node_id` or `port_id`
  - for backward compatibility, `tgraph.get_links("NODE_ID")` returns links for that node
- `tgraph.get_links_for_node(node_id)` -> `list[dict]`
- `tgraph.find_paths(source_id, target_id, cutoff=None)` -> `list[list[str]]`
- `tgraph.find_path(source_id, target_ids)` -> `list[str] | None`
- `tgraph.check_reachability(source_id, target_id)` -> `bool`
- `tgraph.is_reachable(source_id, target_id, via=None)` -> `bool`
- `tgraph.nodes` and `tgraph.links` are available as lists
- Safe builtins include `type` and `isinstance` for schema checks inside custom validator scripts.

### Link dict surface exposed to custom script

- Canonical keys: `id`, `from_port`, `to_port`, `from_node`, `to_node`
- `from_port` and `to_port` values are port id strings, not embedded port objects.
- To inspect endpoint IP/CIDR, fetch the endpoint node with `get_node(...)` and look up the matching port by `id`.
- `get_link(link_id)` and `list_links()` expose only the canonical keys above
- When using a relative `list_links(...)` query with `node_id` or `port_id`, each returned link also exposes `peer_node` and `peer_port`
- Do not rely on `source`, `target`, `ends`, or `ports`
- Do not assume undocumented raw graph keys beyond this surface

## Low-level mutation tool semantics

### Structured tool-call argument rules

- Tool calls use structured JSON arguments.
- Do not JSON-encode nested lists or objects as strings.
- `ports` must be an actual JSON array of objects when calling `update_node`.
- `constraint_ids` must be an actual JSON array, and `args`, `checkpoint`, `image`, and `flavor` must be actual JSON objects.
- Invalid `update_node` tool argument: `{"node_id": "R_CORE", "ports": "<JSON string array>"}`
- Valid `update_node` tool argument: `{"node_id": "R_CORE", "ports": [{"id": "R_CORE_p1", "ip": "10.10.10.1", "cidr": "10.10.10.0/24"}]}`
- If a tool returns a type error such as `Input should be a valid list`, fix the argument type before retrying. Do not repeat the same JSON-string payload.

- `topology_view()`
  - returns compressed `{nodes, links}` only
- `find_checkpoints(node_ids=None, constraint_ids=None, cidrs=None, query=None, limit=10)`
  - returns authored checkpoints from the current stage that best match the supplied node ids, constraint ids, CIDRs, or free-text query
  - use this when the injected candidate checkpoint subset is insufficient
- `get_checkpoint(checkpoint_id)`
  - returns the full authored checkpoint object for the requested checkpoint id
- `add_checkpoint(checkpoint)`
  - appends a new authored checkpoint to the current stage artifact
  - `checkpoint.id` is required
  - returns `ok: false` with `checkpoint_id_required` if `id` is missing
  - returns `ok: false` with `checkpoint_id_exists` if the id already exists
- `update_checkpoint(checkpoint_id, func=None, description=None, constraint_ids=None, args=None)`
  - updates fields on an existing authored checkpoint
  - returns `ok: false` with `checkpoint_id_unknown` if the id does not exist
- `remove_checkpoint(checkpoint_id)`
  - removes an authored checkpoint from the current stage artifact
  - returns `ok: false` with `checkpoint_id_unknown` if the id does not exist
- `get_validator_script()`
  - returns the current stage validator script source
- `replace_validator_script(script)`
  - replaces the current stage validator script source
- `get_node(node_id)`
  - returns the full node object
- `get_nodes(node_ids=None)`
  - returns full node objects
  - when `node_ids` is omitted, returns all nodes
  - when `node_ids` is supplied, returns nodes in the requested order
- `get_link(link_id)`
  - returns the full link object
- `get_links(link_ids=None, node_id=None, port_id=None)`
  - returns full link objects
  - when `link_ids` is supplied, returns links in the requested order
  - otherwise filters by optional `node_id` or `port_id`
- `validate()`
  - validates the current graph
  - in stage repair, this includes the current authored F1-F4 stack when stage checkpoints or a validator script are supplied
- `add_node(node_id, type, label, image=None, flavor=None)`
  - creates a node
- `update_node(node_id, ...)`
  - can update node fields
  - for `ports`, it may only update `ip` and `cidr` on existing port ids
  - it cannot add, remove, or rename ports
  - ports must be an actual JSON array of objects, not a JSON-encoded string
- `add_link(from_port, to_port, from_node=None, to_node=None, from_ip="", from_cidr="", to_ip="", to_cidr="")`
  - creates a link
  - can materialize missing ports when `from_node` or `to_node` are provided
  - re-adding the same endpoint pair is idempotent and may update endpoint addressing
- `update_link(link_id, from_port, to_port, from_node=None, to_node=None, from_ip="", from_cidr="", to_ip="", to_cidr="")`
  - updates an existing link atomically
  - can rewire the link to different endpoint ports
  - can materialize missing ports when `from_node` or `to_node` are provided
  - updates endpoint addressing when IP/CIDR values are supplied
- `remove_link(link_id)`
  - removes a link only
- `remove_node(node_id, cascade=True)`
  - removes a node
  - when `cascade=True`, incident links are removed too
