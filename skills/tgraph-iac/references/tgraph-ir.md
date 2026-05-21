# TGraph IR

TGraph artifacts are stage envelopes around a canonical graph.

Logical envelope:

```json
{
  "tgraph_logical": {"profile": "logical.v1", "nodes": [], "links": []},
  "logical_checkpoints": [],
  "logical_validator_script": null
}
```

Physical envelope:

```json
{
  "tgraph_physical": {"profile": "taal.default.v1", "nodes": [], "links": []},
  "physical_checkpoints": [],
  "physical_validator_script": null
}
```

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
{"id": "R1_p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}
```

Link shape:

```json
{"id": "R1_p1--SW1_p1", "from_port": "R1_p1", "to_port": "SW1_p1"}
```

Link ids are canonicalized from sorted endpoint ports. `from_node` and `to_node` are inferred during normalization. Do not invent alternate fields such as `source`, `target`, `a`, `b`, `connected`, or nested endpoint objects inside the graph itself.

