# Query

## Purpose
Provide stable topology lookups and graph algorithms without exposing raw NetworkX objects to the agent.

## Accepted Input
A canonical TGraph model or dict payload.

## Returned Output
Direct object lookups and graph-level results such as:

- `get_node(node_id)`
- `get_link(link_id)`
- `get_port(port_id)`
- `list_nodes(type=None)`
- `list_links(node_id=None, port_id=None)`
- `ports_of(node_id)`
- `links_of(node_id_or_port_id)`
- `neighbors(node_id)`
- `degree(node_id)`
- `connected_components()`
- `shortest_path(src_node, dst_node)`

## Common Error Codes
- `query_node_not_found`
- `query_link_not_found`
- `query_port_not_found`
- `query_invalid_cidr`

## Minimal Example
```json
{"profile": "logical.v1", "nodes": [], "links": []}
```

## Agent Usage Guidance
Use direct query helpers when you need exact `node` or `link` objects.

Use graph-level helpers when you need topology reasoning such as:

- connectivity
- neighboring nodes
- pathfinding

The adapter may use NetworkX internally, but the supported interface is the `tgraph` query surface, not the raw graph object.
