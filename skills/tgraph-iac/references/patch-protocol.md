# Patch Protocol

Use `scripts/tgraph_apply_patch.py` as the only write path.

## Envelope

```json
{
  "intent": "repair missing link",
  "graph_patch": [],
  "checkpoint_patch": [],
  "validator_patch": null,
  "options": {
    "stage": "logical",
    "validate": ["f1", "f2", "f3", "f4"],
    "dry_run": false,
    "include_artifact": false
  }
}
```

## Graph Operations

Create or merge a node:

```json
{"op": "ensure_node", "id": "R1", "type": "router", "label": "Core Router"}
```

Ensure a link and create missing ports:

```json
{
  "op": "ensure_link",
  "a": {"node": "R1", "port": "R1_p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"},
  "b": {"node": "SW1", "port": "SW1_p1", "cidr": "10.0.0.0/30"},
  "reconnect": false
}
```

Remove a link:

```json
{"op": "remove_link", "id": "R1_p1--SW1_p1"}
```

Remove a node:

```json
{"op": "remove_node", "id": "OLD_NODE", "cascade": true}
```

`ensure_link` rejects already-connected endpoint ports unless `reconnect` is true. With `reconnect: true`, old incident links are removed before the requested link is created.

## Checkpoint Operations

```json
{
  "op": "ensure_checkpoint",
  "id": "cp_connect_r1_sw1",
  "func": "connect_nodes",
  "description": "R1 must connect to SW1.",
  "constraint_ids": ["lc_001"],
  "args": {"node_a": "R1", "node_b": "SW1"}
}
```

```json
{"op": "remove_checkpoint", "id": "cp_wrong_gateway"}
```

## Validator Operation

Replace the whole validator script:

```json
{
  "op": "replace_script",
  "script": "def check_x(tgraph, **kwargs):\n    return []\n"
}
```

Do not patch validator scripts by string offsets.

## Result

`ok` means the candidate passed validation. `committed` means the script may write the output artifact. `accepted_ops` lists operations applied to the candidate copy. `rejected_ops` lists schema or conflict failures. `validation` contains F1-F4 issues. `artifact` is null unless requested.

Common errors:

- `backend_resolution_error`
- `artifact_shape_error`
- `patch_schema_error`
- `op_conflict`
- `validation_failed`
- `export_error`

