# TGraphEditor API

Mutation files call `mutate(tgraph)` on a write-capable editor.

```python
def mutate(tgraph):
    tgraph.ensure_direct_link("WEB", "SW_DMZ")
    tgraph.ensure_chain(["WEB", "SW_DMZ", "R_CORE"])
    tgraph.ensure_subnet("SW_DMZ", cidr="10.10.10.0/24")
    tgraph.ensure_interface("R_CORE", segment="SW_DMZ", cidr="10.10.10.0/24", ip="10.10.10.1")  # segment is required: neighboring node id (parameter, not an IR field)
    tgraph.set_node_image("FIREWALL", {"id": "vyos-fw", "name": "VyOS"})
    tgraph.set_node_flavor("WEB", vcpu=2, ram=4096, disk=20)
    return tgraph
```

Prefer idempotent `ensure_*` operations. Use `link_key` for parallel links.

`segment` is always a function parameter referring to another node id — never an IR field.
