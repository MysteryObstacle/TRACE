# Physical Authoring

## Purpose
Guide physical-stage authoring toward the semantic TGraph patch API without mutating approved logical connectivity.

## Preferred Patch Ops
- `update_node`
- `batch_update_nodes`

## Optional Query Helpers
- `get_node(node_id)`
- `get_link(link_id)`
- `list_links(node_id=None, port_id=None)`

## Minimal Example
```json
{
  "physical_patch_ops": [
    {
      "op": "batch_update_nodes",
      "node_ids": ["PLC1", "PLC2"],
      "changes": {
        "image": {"id": "openplc-v3", "name": "OpenPLC v3"},
        "flavor": {"vcpu": 2, "ram": 2048, "disk": 20}
      }
    }
  ]
}
```

## Common Pitfalls
- Physical stage should normally not add or remove logical links
- `disconnect_nodes` keeps ports intact, so use it only when a repair truly changes connectivity
- Prefer direct query helpers over manual graph scans when checking whether a link already exists
