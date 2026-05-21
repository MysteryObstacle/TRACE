# TGraph Custom Validator SDK

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
- `tgraph.get_link(link_id)` -> `dict | None`
- `tgraph.list_links(node_id=None, port_id=None)` -> `list[dict]`
- `tgraph.get_links(link_ids=None, node_id=None, port_id=None)` -> `list[dict]`
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
- When using a relative `list_links(...)` query with `node_id` or `port_id`, each returned link also exposes `peer_node` and `peer_port`.
- Do not rely on `source`, `target`, `ends`, or `ports`.
