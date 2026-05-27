# Checkpoint Authoring

One Python file per stage: `logical/checkpoints.py` or `physical/checkpoints.py`.

Each constraint id `lc9` needs:

```python
def check_lc9(tgraph):
    return tgraph.check_chain(["WEB", "SW_DMZ", "R_CORE"])
```

Rules:
- Function name must be `check_<constraint_id>`.
- Prefer one-line `tgraph.check_*` calls for formal kinds.
- Return `[]` when satisfied, or issue dicts / `tgraph.issue(...)`.
- Issues should include `details.repair_target` (`graph`, `metadata`, or `checkpoint`).

Read constraints from `ground/logical_constraints.json` or `ground/physical_constraints.json`.
