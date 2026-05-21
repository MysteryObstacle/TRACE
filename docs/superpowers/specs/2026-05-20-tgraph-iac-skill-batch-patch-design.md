# TGraph IaC Skill Batch Patch Design

## Goal

Create an installable `tgraph-iac` Skill for Codex, Claude Code, and similar coding agents. The Skill should let agents generate, inspect, repair, validate, and export TGraph-based IaC artifacts without exposing the current low-level CRUD tool surface.

The core design shift is to replace agent-facing transaction/CRUD operations with a declarative batch patch protocol. The existing TRACE LangChain/LangGraph runtime must keep working while the new Skill and patch API mature.

## Context

TRACE currently provides:

- TGraph IR schema and normalization.
- Logical and physical artifact stages.
- F1-F4 validation, including authored checkpoints and custom validator scripts.
- Low-level node/link/checkpoint tools through `BoundTGraphTools`.
- A `runtime -> transaction -> commit` mutation path.

The current mutation surface is difficult for agents:

- It exposes many low-level tools at once.
- It requires agents to remember fragile argument shapes, especially nested JSON for ports/checkpoints.
- Each public mutation starts and commits its own transaction, so the transaction abstraction does not provide batch atomicity.
- Repair prompts must carry many guardrails that should belong in the protocol.

## Design Principles

- Make the Skill installable and usable from any project directory.
- Keep TRACE as the authoritative backend implementation.
- Avoid duplicating TGraph logic inside the Skill.
- Expose a small, stable agent-facing interface.
- Use idempotent `ensure_*` operations where possible.
- Use explicit `remove_*` operations for destructive changes.
- Apply a coherent batch on a candidate copy, then normalize and validate once.
- Do not commit invalid patches by default.
- Preserve the current LangChain/LangGraph pipeline during v1.

## Skill Shape

The installable Skill should be named `tgraph-iac`.

```text
tgraph-iac/
  SKILL.md
  agents/
    openai.yaml
  references/
    patch-protocol.md
    tgraph-ir.md
    validation.md
    agent-workflows.md
    export-targets.md
  scripts/
    trace_backend.py
    tgraph_inspect.py
    tgraph_apply_patch.py
    tgraph_validate.py
    tgraph_export.py
```

`SKILL.md` should stay short. It should describe the agent workflow and tell the agent when to load reference files. Detailed schemas and examples belong in `references/`.

## TRACE Backend Resolution

Skill scripts must run from arbitrary project directories. They must locate TRACE through a shared `scripts/trace_backend.py` helper.

Resolution order:

1. CLI argument: `--trace-root D:/Projects/Trace`
2. Environment variable: `TGRAPH_TRACE_ROOT=D:/Projects/Trace`
3. Environment variable: `TGRAPH_TRACE_PYTHON=...`
4. The current Python environment, if TRACE is already installed
5. A clear `backend_resolution_error`

When `--trace-root` or `TGRAPH_TRACE_ROOT` is used, the helper should prepend `<trace-root>/src` to `sys.path`, import `trace.tools.tgraph`, and verify the loaded module path is under the expected root.

This path check is required because the package name `trace` can collide with Python's standard-library `trace` module.

## Public Scripts

The Skill exposes four stable script entrypoints.

```text
tgraph_inspect.py
tgraph_apply_patch.py
tgraph_validate.py
tgraph_export.py
```

All scripts accept explicit file paths. They should output machine-readable JSON to stdout. They should only write files when `--out` is provided.

### `tgraph_inspect.py`

Reads an artifact envelope and returns focused context.

Example calls:

```powershell
python tgraph_inspect.py --artifact artifact.json --query topology
python tgraph_inspect.py --artifact artifact.json --query node --id R1
python tgraph_inspect.py --artifact artifact.json --query links --node R1
python tgraph_inspect.py --artifact artifact.json --query checkpoints --text gateway
```

Purpose: keep agents from repeatedly reading or emitting full artifacts.

### `tgraph_apply_patch.py`

The only write entrypoint.

```powershell
python tgraph_apply_patch.py --artifact artifact.json --patch patch.json --stage logical --out artifact.json
```

It must:

1. Read the artifact envelope.
2. Read the batch patch.
3. Apply all operations to a candidate copy.
4. Normalize the candidate artifact.
5. Validate the candidate artifact.
6. Write `--out` only when `ok=true` and not dry-run.

Default output should not include the full artifact. The full artifact is returned only when `patch.options.include_artifact=true` or `--include-artifact` is supplied.

### `tgraph_validate.py`

Validates an artifact without modifying it.

```powershell
python tgraph_validate.py --artifact artifact.json --stage physical --levels f1,f2,f3,f4
```

### `tgraph_export.py`

Exports a validated artifact to a target IaC format.

```powershell
python tgraph_export.py --artifact artifact.json --target terraform --out ./generated
```

The first version may keep exporter support minimal, but the interface should be stable enough for later Terraform, OpenTofu, Ansible, or other exporters.

## Artifact Envelope

Logical artifact envelope:

```json
{
  "tgraph_logical": {},
  "logical_checkpoints": [],
  "logical_validator_script": null
}
```

Physical artifact envelope:

```json
{
  "tgraph_physical": {},
  "physical_checkpoints": [],
  "physical_validator_script": null
}
```

Scripts use `--stage logical|physical` to select the field group. If `--stage` is omitted, scripts may infer the stage only when exactly one field group is present. Ambiguous artifacts must fail with `artifact_shape_error`.

## Batch Patch Protocol

Patch envelope:

```json
{
  "intent": "repair missing gateway link",
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

### Graph Patch Operations

`ensure_node` performs upsert plus merge. It creates the node if missing and updates only fields present in the operation.

```json
{
  "op": "ensure_node",
  "id": "R1",
  "type": "router",
  "label": "Core Router",
  "image": null,
  "flavor": null
}
```

`ensure_link` ensures two endpoint ports are linked. Missing ports are created when their endpoint includes `node`.

```json
{
  "op": "ensure_link",
  "a": {
    "node": "R1",
    "port": "R1_p1",
    "ip": "10.0.0.1",
    "cidr": "10.0.0.0/30"
  },
  "b": {
    "node": "SW1",
    "port": "SW1_p1"
  },
  "reconnect": false
}
```

If either endpoint port is already connected to a different port:

- `reconnect=false` or omitted: reject the operation with `op_conflict`.
- `reconnect=true`: remove the old incident link and create/update the requested link.

`remove_link` removes a link by id.

```json
{
  "op": "remove_link",
  "id": "R1_p1--SW1_p1"
}
```

`remove_node` removes a node. With `cascade=true`, incident links and ports are removed too.

```json
{
  "op": "remove_node",
  "id": "OLD_NODE",
  "cascade": true
}
```

### Checkpoint Patch Operations

`ensure_checkpoint` performs upsert plus merge. `id` and `func` are required.

```json
{
  "op": "ensure_checkpoint",
  "id": "cp_connect_r1_sw1",
  "func": "connect_nodes",
  "description": "R1 must connect to SW1.",
  "constraint_ids": ["lc_001"],
  "args": {
    "node_a": "R1",
    "node_b": "SW1"
  }
}
```

`remove_checkpoint` removes a checkpoint by id.

```json
{
  "op": "remove_checkpoint",
  "id": "cp_wrong_gateway"
}
```

### Validator Patch Operations

Validator scripts are replaced as a whole. Local string patching is intentionally out of scope.

```json
{
  "op": "replace_script",
  "script": "def check_x(tgraph, **kwargs):\n    return []\n"
}
```

## Apply Result

Default result shape:

```json
{
  "ok": true,
  "committed": true,
  "accepted_ops": [],
  "rejected_ops": [],
  "diff": {
    "nodes_added": [],
    "nodes_updated": [],
    "nodes_removed": [],
    "links_added": [],
    "links_removed": [],
    "ports_added": [],
    "ports_updated": [],
    "checkpoints_added": [],
    "checkpoints_updated": [],
    "checkpoints_removed": [],
    "validator_script_replaced": false
  },
  "validation": {
    "ok": true,
    "issues": []
  },
  "artifact": null,
  "error": null
}
```

`accepted_ops` means operations that succeeded on the candidate copy. `committed` means the artifact was written to disk.

When validation fails, the result may include accepted operations and a diff, but `committed` remains false unless a future version explicitly supports invalid commits.

## Error Model

All failures must be returned as stable JSON, not raw tracebacks.

Error codes:

- `backend_resolution_error`: TRACE root, Python, import, or package path problem.
- `artifact_shape_error`: envelope missing required fields or stage inference is ambiguous.
- `patch_schema_error`: invalid patch JSON, unknown op, or missing required fields.
- `op_conflict`: semantic conflict such as a connected port with `reconnect=false`.
- `validation_failed`: patch is structurally applicable but F1-F4 validation fails.
- `export_error`: unsupported target or exporter failure.

Example:

```json
{
  "ok": false,
  "committed": false,
  "accepted_ops": [],
  "rejected_ops": [
    {
      "section": "graph_patch",
      "index": 0,
      "op": "ensure_link",
      "error": {
        "code": "op_conflict",
        "message": "port R1_p1 is already linked to SW2_p1"
      }
    }
  ],
  "diff": {},
  "validation": null,
  "artifact": null,
  "error": {
    "code": "op_conflict",
    "message": "one or more patch operations were rejected"
  }
}
```

## Agent Workflow

`SKILL.md` should instruct agents to follow this loop:

1. Locate the TRACE backend.
2. Read or create an artifact envelope.
3. Use `tgraph_inspect.py` for focused context.
4. Build one coherent batch patch.
5. Use dry-run for risky changes.
6. Apply the patch through `tgraph_apply_patch.py`.
7. Validate through `tgraph_validate.py`.
8. Iterate using `rejected_ops` and `validation.issues`.
9. Export only after validation passes.

Generation workflow:

```text
natural language intent
-> create initial artifact envelope
-> ensure_node / ensure_link for topology
-> ensure_checkpoint for grounded constraints
-> validate
-> export
```

Repair workflow:

```text
existing artifact + validation issues
-> inspect topology / target nodes / candidate checkpoints
-> decide whether graph, checkpoint, or validator script is wrong
-> construct minimal patch
-> apply + validate
-> iterate
```

Export workflow:

```text
existing validated artifact
-> validate
-> export target IaC
```

## Compatibility And Migration

The first implementation must not break the existing TRACE LangChain/LangGraph pipeline.

Migration sequence:

1. Add the Skill and new batch patch scripts.
2. Add a new patch API in TRACE, such as `trace.tools.tgraph.patch`, without deleting existing runtime or transaction code.
3. Keep `BoundTGraphTools`, `TGraphRuntime`, and `TGraphTransaction` working for current logical/physical repair nodes.
4. Point Skill scripts at the new patch API.
5. After the Skill protocol is stable, migrate logical/physical repair agents from low-level CRUD tools to batch patch.
6. Only after all callers are migrated, delete `transaction.py` or reduce it to a private helper.

In v1, "remove transaction" is a target architecture decision, not a first-step source deletion.

## Internal TRACE Module Direction

Long-term module shape:

```text
model.py        TGraph schema and normalization
query.py        graph and artifact inspection
patch.py        batch patch application and diff
validate/       F1-F4 validators
export/         target IaC exporters
```

`runtime.py` may remain as a thin document/query/canonicalization layer if useful. The transaction concept should not be public unless it supports true multi-operation atomicity.

## Testing Plan

Unit tests:

- TRACE backend resolver.
- `ensure_node` create and merge behavior.
- `ensure_link` idempotency.
- `ensure_link` conflict with `reconnect=false`.
- `ensure_link` rewiring with `reconnect=true`.
- `remove_link`.
- `remove_node` with cascade behavior.
- `ensure_checkpoint`.
- `remove_checkpoint`.
- `replace_script`.
- Diff generation.

CLI tests:

- Run scripts from arbitrary cwd using `--trace-root`.
- Dry-run never writes output.
- `include_artifact` controls result size.
- Stage inference succeeds only when unambiguous.
- Errors are stable JSON.

Workflow tests:

- Generate a small logical artifact from intent.
- Repair a missing-link validation issue.
- Repair an incorrect checkpoint without forcing graph changes.
- Validate a physical artifact while preserving logical topology.
- Export a validated artifact.

Skill validation:

- Run the Skill through the skill validation script.
- Forward-test with a fresh agent on a small artifact repair task. The fresh agent should only see the Skill and raw artifact, not this design discussion.

## Non-Goals For V1

- Direct JSON Patch path operations.
- Long-lived transaction handles.
- Partial string patching of validator scripts.
- Automatic invalid commits.
- Full exporter coverage for every IaC target.
- Immediate migration of current LangGraph repair nodes.

