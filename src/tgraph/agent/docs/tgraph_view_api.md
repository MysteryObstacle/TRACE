# TGraphView API

Read-only graph inspection inside checkpoint functions.

```python
tgraph.node("WEB")
tgraph.nodes(type="switch")
tgraph.port("R_CORE", "_SW_DMZ-1")
tgraph.links(between=["WEB", "SW_DMZ"])
tgraph.neighbors("WEB")
tgraph.paths("WEB", "R_CORE", limit=5)
tgraph.cidrs()
```

Use `link_key` when checking a specific parallel link between two nodes.
