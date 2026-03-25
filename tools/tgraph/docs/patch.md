# Patch

## Purpose
Apply semantic topology patch operations without making the agent manually choreograph node, port, and link consistency.

## Accepted Input
A canonical graph plus one or more patch operations such as:

- `add_nodes`
- `remove_nodes`
- `connect_nodes`
- `disconnect_nodes`
- `update_node`
- `batch_update_nodes`

Legacy low-level ops may still exist for compatibility, but semantic ops are the preferred interface.

## Returned Output
A `PatchResult` with:

- `ok`
- `graph`
- `issues`

## Common Error Codes
- `patch_unknown_op`
- `patch_node_not_found`
- `patch_port_owner_mismatch`
- `patch_port_already_linked`
- `patch_remove_connected_port_forbidden`
- `patch_link_not_found`
- `patch_invalid_update_payload`

## Minimal Example
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

## Agent Usage Guidance
Prefer `connect_nodes` and `disconnect_nodes` for connectivity changes.

Use `update_node` and `batch_update_nodes` for node-local fields such as:

- `label`
- `type`
- `image`
- `flavor`
- `changes.ports`
- `remove.ports`

Remember:

- `node.id` is immutable
- `port.id` is globally unique and immutable
- `disconnect_nodes` does not delete endpoint ports
- removing a linked port must fail until the link is disconnected
