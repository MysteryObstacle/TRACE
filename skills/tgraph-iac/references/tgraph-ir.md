# TGraph IR

TRACE stage artifacts always use the uniform outer shape:

```json
{
  "graph": {"stage": "logical", "nodes": [], "links": []},
  "constraint_files": {"logical": "ground/logical_constraints.json"},
  "checkpoint_files": {"logical": "logical/checkpoints.py"}
}
```

The inner `graph` field is the canonical standalone TGraph document:

```json
{"stage": "logical", "nodes": [], "links": []}
```

`graph.stage` is the only stage marker. There is no extra schema marker field and no stage-specific graph field name.

Node shape:

```json
{
  "id": "R1",
  "type": "router",
  "label": "Core Router",
  "ports": [],
  "image": null,
  "flavor": null
}
```

Supported node types are `switch`, `router`, and `computer`.

Port shape:

```json
{"id": "_SW1-1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}
```

Link shape:

```json
{"id": "R1-SW1-1", "from_node": "R1", "from_port": "_SW1-1", "to_node": "SW1", "to_port": "_R1-1"}
```

Link ids use `NODE-NODE-key`. Port ids are node-scoped and use `_PEER-key`. Node ids should use uppercase letters, digits, and underscores; avoid hyphens in node ids because link ids use hyphens as separators. Do not invent alternate fields such as `source`, `target`, `a`, `b`, `connected`, or nested endpoint objects inside the graph itself.

`tgraph_export.py --target tgraph-json` writes the standalone canonical `graph` document, not the outer TRACE stage artifact.

