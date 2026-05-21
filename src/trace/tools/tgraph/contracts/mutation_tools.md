# TGraph Mutation Tools

## Low-level mutation tool semantics

### Structured tool-call argument rules

- Tool calls use structured JSON arguments.
- Do not JSON-encode nested lists or objects as strings.
- `ports` must be an actual JSON array of objects when calling `update_node`.
- `constraint_ids` must be an actual JSON array, and `args`, `checkpoint`, `image`, and `flavor` must be actual JSON objects.
- If a tool returns a type error such as `Input should be a valid list`, fix the argument type before retrying. Do not repeat the same JSON-string payload.

- `topology_view()`
  - returns compressed `{nodes, links}` only
- `find_checkpoints(node_ids=None, constraint_ids=None, cidrs=None, query=None, limit=10)`
  - returns authored checkpoints from the current stage that best match the supplied node ids, constraint ids, CIDRs, or free-text query
- `get_checkpoint(checkpoint_id)`
  - returns the full authored checkpoint object for the requested checkpoint id
- `add_checkpoint(checkpoint)`
  - appends a new authored checkpoint to the current stage artifact
- `update_checkpoint(checkpoint_id, func=None, description=None, constraint_ids=None, args=None)`
  - updates fields on an existing authored checkpoint
- `remove_checkpoint(checkpoint_id)`
  - removes an authored checkpoint from the current stage artifact
- `get_validator_script()`
  - returns the current stage validator script source
- `replace_validator_script(script)`
  - replaces the current stage validator script source
- `get_node(node_id)`
  - returns the full node object
- `get_nodes(node_ids=None)`
  - returns full node objects
- `get_link(link_id)`
  - returns the full link object
- `get_links(link_ids=None, node_id=None, port_id=None)`
  - returns full link objects
- `validate()`
  - validates the current graph
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
