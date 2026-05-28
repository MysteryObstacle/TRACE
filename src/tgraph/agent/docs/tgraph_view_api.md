# TGraphView API

Read-only graph inspection inside checkpoint functions.

```python
tgraph.node("WEB")
tgraph.get_node("WEB")        # legacy alias for node()
tgraph.nodes(type="switch")
tgraph.port("R_CORE", "_SW_DMZ-1")
tgraph.ports(node_id="R_CORE")
tgraph.get_ports("R_CORE")    # legacy alias for ports(node_id=...)
tgraph.links(between=["WEB", "SW_DMZ"])
tgraph.neighbors("WEB")
tgraph.paths("WEB", "R_CORE", limit=5)
tgraph.cidrs()
tgraph.ip_in_cidr("10.10.10.2", "10.10.10.0/24")
tgraph.ip_in_subnet("10.10.10.2", "10.10.10.0/24")  # legacy alias
```

Use `link_key` when checking a specific parallel link between two nodes.

Checkpoint helpers such as `check_interface(...)` return a list of validation issues, not interface payloads. Use `ports(...)` / `get_ports(...)` when you need to inspect port `ip` or `cidr` values directly.
