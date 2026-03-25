# Logical Authoring

## Purpose
Guide logical-stage authoring toward the semantic TGraph patch API.

## Preferred Patch Ops
- `update_node`
- `batch_update_nodes`
- `connect_nodes`
- `disconnect_nodes`

## Typical Pattern
Use `update_node` to set node-local fields and port upserts, then use `connect_nodes` to realize logical adjacency.

## Minimal Example
```json
{
  "logical_patch_ops": [
    {
      "op": "update_node",
      "node_id": "PLC1",
      "changes": {
        "type": "computer",
        "label": "PLC1",
        "ports": [
          {"id": "PLC1:eth0", "ip": "", "cidr": ""}
        ]
      }
    },
    {
      "op": "connect_nodes",
      "from": {
        "node_id": "PLC1",
        "port": {"id": "PLC1:eth0", "ip": "", "cidr": ""}
      },
      "to": {
        "node_id": "SW1",
        "port": {"id": "SW1:ge0/1", "ip": "", "cidr": "10.0.0.0/24"}
      }
    }
  ]
}
```

## Common Pitfalls
- Do not try to rename `node.id` or `port.id`
- Do not delete a linked port before disconnecting it
- Prefer `get_link(link_id)` or `list_links(...)` over manual payload scans during repair
