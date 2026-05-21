# TGraph Transaction Ops v1 (Node/Link-Only)

## Goal

Add a minimal, agent-friendly editing surface for TGraph transactions that avoids explicit port tools. Agents should operate only on nodes and links, while still being able to create and update port data via link operations.

This design targets the runtime transaction layer and the tool protocol layer used by repair agents.

## Scope

In-scope:
- Transaction operations: `add_node`, `update_node`, `add_link`, `remove_link`, `remove_node`
- Port data (`ip/cidr`) creation/update as part of link operations
- Port data (`ip/cidr`) updates via `update_node` (existing ports only)
- Tool protocol (`tx_apply`) support for the above operations

Out-of-scope:
- Dedicated `add_port` / `update_port` tools
- Port `attrs` beyond `ip/cidr`
- High-level semantic repair helpers (e.g., attach/detach, gateway heuristics)

## Design Principles

- Keep the tool surface minimal: only nodes and links are exposed.
- Port creation and updates happen implicitly through link operations.
- Updates are *partial* (fields not provided are left unchanged).
- Validation still enforces: one port participates in at most one link.

## Transaction API

### `add_node`

Signature:
- `add_node(node_id, type, label, image=None, flavor=None)`

Behavior:
- Creates a new node with an empty port list.
- Raises if `node_id` already exists.

### `update_node`

Signature:
- `update_node(node_id, **attrs, ports=[...])`

Behavior:
- Partial update of node fields (label/type/image/flavor).
- `ports` is optional and supports **partial updates only**.
- Each port update must reference an existing `port.id`.
- Port updates can only change `ip/cidr`.
- Port `id` cannot be changed.
- Ports cannot be added or removed via `update_node`.
- If a port id does not exist, raise an error.

### `add_link`

Signature:
- `add_link(from_port, to_port, from_node=None, to_node=None, from_ip="", from_cidr="", to_ip="", to_cidr="")`

Behavior:
- If `from_port` or `to_port` exists, updates its `ip/cidr` only if provided.
- If a port does not exist, its matching `from_node`/`to_node` must be provided so the port can be created on that node.
- Adds a link if no undirected link between the two ports exists.
- If a link already exists, does not add a duplicate; still performs port updates.

### `remove_link`

Signature:
- `remove_link(link_id)`

Behavior:
- Removes the link.
- Does not delete ports; ports remain on their owner nodes.

### `remove_node`

Signature:
- `remove_node(node_id, cascade=True)`

Behavior:
- `cascade=True`: removes the node, its ports, and any links attached to those ports.
- `cascade=False`: raises if the node still has ports or incident links.

## Tool Protocol (`tx_apply`)

Allowed `op` values:
- `add_node`
- `update_node`
- `add_link`
- `remove_link`
- `remove_node`

`add_link` payload uses only `ip/cidr` for port attributes.
`update_node` port payload uses only `ip/cidr` for existing ports.

## Validation Expectations

- Port uniqueness across nodes is enforced.
- Link endpoints must exist after any link operation.
- A port may participate in at most one link (existing `f3` rule).

## Example Flows

### Create two routers and connect them with IPs

1. `add_node("R1", "router", "R1")`
2. `add_node("R2", "router", "R2")`
3. `add_link("R1:p1", "R2:p1", from_node="R1", to_node="R2", from_ip="10.0.0.1", from_cidr="10.0.0.0/30", to_ip="10.0.0.2", to_cidr="10.0.0.0/30")`

### Rewire a link and update IP for one side

1. `remove_link("R1:p1--R2:p1")`
2. `add_link("R1:p2", "R2:p1", from_node="R1", from_ip="10.0.0.9")`

## Testing

Add unit tests covering:
- `add_node` creates nodes
- `add_link` creates ports when node id is supplied
- `add_link` fails if endpoint port is missing and node id is not supplied
- `update_link` rewires endpoints and updates port `ip/cidr`
- `update_node` updates `ip/cidr` for existing ports and rejects unknown port ids
- `remove_node(cascade=True)` removes incident links and ports
- `remove_link` removes the link but keeps ports

## Risks / Open Questions

- `update_node` does not update ports in v1 to keep tool surface small.
- For now, only `ip/cidr` are supported for port updates; `attrs` can be added later if needed.
