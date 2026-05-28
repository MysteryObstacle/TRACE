# Artifact Files

TRACE stage artifacts use the same outer shape:

```json
{
  "graph": {"stage": "logical", "nodes": [], "links": []},
  "constraint_files": {"logical": "ground/logical_constraints.json"},
  "checkpoint_files": {"logical": "logical/checkpoints.py"}
}
```

Ground stage writes canonical constraint support files:

- `ground/logical_constraints.json`
- `ground/physical_constraints.json`

Logical stage writes:

- `logical/checkpoints.py`

Physical stage writes:

- `physical/checkpoints.py`

Constraint files are JSON objects keyed by constraint id:

```json
{
  "lc9": {
    "kind": "logical.topology.chain",
    "statement": "explicit chain WEB -> SW_DMZ -> R_CORE."
  }
}
```

The validator reads constraints for metadata and coverage. It does not parse `statement` as executable semantics.
