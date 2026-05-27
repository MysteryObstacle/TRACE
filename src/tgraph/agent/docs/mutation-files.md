# Mutation Files

Graph repair uses a Python mutation file with one entrypoint:

```python
def mutate(tgraph):
    tgraph.ensure_chain(["WEB", "SW_DMZ", "R_CORE"])
    tgraph.ensure_subnet("SW_DMZ", cidr="10.10.10.0/24")
```

Mutation files receive a `TGraphEditor`, not a raw dict.

Available editor operations:

- `ensure_node(node_id, type="computer", label=None)`
- `ensure_direct_link(node_a, node_b, link_key=None)`
- `ensure_chain(nodes, link_keys=None)`
- `ensure_ring(nodes, link_keys=None)`
- `ensure_star(center=..., leaves=..., link_keys=None)`
- `ensure_mesh(nodes)`
- `ensure_subnet(switch, cidr=...)`
- `ensure_interface(node, segment=..., cidr=..., ip=None, link_key=None)`
- `set_image(node, image_id, name=None)`
- `set_flavor(node, vcpu=..., ram=..., disk=...)`
- `remove_direct_link(node_a, node_b, link_key=None)`
- `remove_links_between(node_a, node_b)`
- `remove_node(node, cascade=True)`

Mutation files run in a sandboxed subprocess and are transactional. A timeout or validation failure leaves the original graph unchanged.

Destructive operations:

- `remove_direct_link` removes the matching link and orphaned endpoint ports.
- `remove_links_between` can remove multiple links between the same nodes and is marked destructive.
- `remove_node(..., cascade=True)` removes incident links and orphaned ports.
