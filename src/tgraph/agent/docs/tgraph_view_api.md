# TGraphView API

Read-only graph inspection inside checkpoint functions.

```python
tgraph.node("WEB")
tgraph.nodes(type="switch")
tgraph.port("R_CORE", "_SW_DMZ-1")
tgraph.ports(node_id="R_CORE")
tgraph.links(between=["WEB", "SW_DMZ"])
tgraph.neighbors("WEB")
tgraph.paths("WEB", "R_CORE", limit=5)
tgraph.cidrs()
tgraph.ip_in_cidr("10.10.10.2", "10.10.10.0/24")
```

Use `link_key` when checking a specific parallel link between two nodes.

`check_interface(...)` and other `check_*` helpers return a list of validation issues, not interface payloads. To read port `ip` or `cidr`, use `ports(...)` or `node(...)`.

## Forbidden legacy names (do not use)

`get_node`, `get_ports`, `ip_in_subnet` — use `node`, `ports`, and `ip_in_cidr` instead.
