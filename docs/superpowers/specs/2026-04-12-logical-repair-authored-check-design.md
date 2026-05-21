# Logical Repair Authored-Check Design

## Goal

Refine the logical-stage validation and repair design so TRACE can repair either the logical graph or authored F4 intent checks without introducing a separate statement compiler layer.

This design keeps grounded constraints as natural-language statements, keeps LLM reasoning in the logical author, and makes repair responsible for localized fixes across the whole logical artifact.

## Approved Decisions

- Keep `ground_artifact.logical_constraints` as the primary realization input for the logical builder.
- Do not introduce a separate `statement -> semantic IR` compiler layer.
- Keep LLM-based interpretation in the logical author; that is the point of using an LLM here.
- Treat logical repair as `logical artifact repair`, not only `graph repair`.
- Allow logical repair to modify:
  - `tgraph_logical`
  - `logical_checkpoints`
  - `logical_validator_script`
- Remove `scope` from validation issues.
- Keep `targets` on validation issues.
- Add issue `provenance` so repair can trace validator failures back to authored checks.
- Use `impl_source: "sdk" | "custom" | "unknown"` to distinguish built-in SDK checks, custom script-backed checks, and unresolved function-origin failures.
- Cover both concrete authored-check failures and script-level validator-script load failures in F4 provenance.
- The graph mutation tool surface should have at least:
  - `add_node`
  - `update_node`
  - `remove_node`
  - `add_link`
  - `update_link`
  - `remove_link`

## Why Not Add A Statement Compiler

The logical author already performs the key semantic interpretation step: it reads grounded natural-language constraints and instantiates executable F4 checks. That is where LLM reasoning is most valuable.

Adding another explicit statement compiler layer would:

- duplicate semantic interpretation logic
- create another intermediate contract to maintain
- risk replacing useful LLM reasoning with brittle rule systems

The real problem is not the absence of a compiler layer. The problem is that downstream repair currently lacks enough provenance and authority to resolve whether a failed F4 result comes from the graph, the authored check, or both.

## Logical Stage Alignment With The Paper

The current pipeline is already structurally close to the paper:

1. `author` instantiates logical checkpoints from grounded logical constraints
2. `prepare` and `builder` construct the logical graph draft
3. `validator` runs F1-F4
4. `repair` performs localized fixes

The main design adjustment is not the stage order. It is strengthening the contract between validation and repair so repair can handle failures in the authored F4 layer directly rather than treating every failure as a graph-only problem.

## Builder Boundary

The logical builder should continue to realize topology primarily from:

- `ground_artifact.node_groups`
- `ground_artifact.logical_constraints`

It should not blindly trust `logical_checkpoints` as a stronger source of truth than grounded constraints. Authored checkpoints may be wrong, incomplete, or overfit to a mistaken interpretation. If the graph, the checkpoints, and the grounded constraints conflict, that conflict should surface to validation and be resolved during repair.

This means:

- grounded constraints remain the main realization contract
- authored checkpoints remain the main F4 validation contract
- repair is the place where collisions are adjudicated

## Repair Scope

Logical repair should be upgraded from "repair the graph until validation passes" to "repair the logical artifact until validation passes."

That means repair can choose among three classes of fix:

1. repair the graph
2. repair authored checkpoints
3. repair the authored custom validator script

Default behavior:

- F1-F3 failures should default to graph repair
- F4 failures should trigger inspection of the related authored check and the related grounded constraint before deciding what to change

Repair should not be forced to route checkpoint/script problems back through author. Localized edits are shorter, cheaper, and better aligned with the paper's repair loop.

## Issue Shape

### Target Shape

```json
{
  "code": "missing_required_link",
  "message": "SW_DMZ is not directly connected to SW_OFFICE",
  "severity": "error",
  "targets": ["SW_DMZ", "SW_OFFICE"],
  "json_paths": [],
  "provenance": {
    "layer": "f4",
    "source": "authored_check",
    "check_id": "C31-check",
    "constraint_ids": ["C31"],
    "func": "connect_nodes",
    "impl_source": "sdk",
    "args": {
      "node_a": "SW_DMZ",
      "node_b": "SW_OFFICE"
    }
  }
}
```

### Field Semantics

- `code`: stable machine-readable failure code
- `message`: human-readable explanation
- `severity`: `error` or `warning`
- `targets`: graph objects or ids most directly involved in the failure
- `json_paths`: relevant graph/document locations when applicable
- `provenance`: where the issue came from

### Provenance Fields

- `layer`: `f1 | f2 | f3 | f4`
- `source`: `builtin | authored_check`
- `check_id`: present when the issue comes from a concrete authored F4 check
- `constraint_ids`: grounded logical constraint ids associated with the check when available
- `func`: the check function name when known
- `impl_source`: `sdk | custom | unknown`
- `args`: concrete check arguments used at execution time when a concrete check invocation exists
- `artifact`: optional authored artifact identifier for script-level failures, for example `logical_validator_script`

### Provenance Rules

F1-F3 issue example:

```json
{
  "layer": "f3",
  "source": "builtin"
}
```

F4 SDK-backed issue example:

```json
{
  "layer": "f4",
  "source": "authored_check",
  "check_id": "cp1",
  "constraint_ids": ["lc1"],
  "func": "connect_nodes",
  "impl_source": "sdk",
  "args": {
    "node_a": "A",
    "node_b": "B"
  }
}
```

F4 custom-check issue example:

```json
{
  "layer": "f4",
  "source": "authored_check",
  "check_id": "cp2",
  "constraint_ids": ["lc2"],
  "func": "check_subnet_isolation",
  "impl_source": "custom",
  "args": {
    "subnet": "10.10.20.0/24"
  }
}
```

F4 validator-script load failure example:

```json
{
  "layer": "f4",
  "source": "authored_check",
  "impl_source": "custom",
  "artifact": "logical_validator_script"
}
```

F4 unresolved function-origin failure example:

```json
{
  "layer": "f4",
  "source": "authored_check",
  "check_id": "cp3",
  "constraint_ids": ["lc3"],
  "func": "check_unknown_rule",
  "impl_source": "unknown",
  "args": {
    "node_id": "HOST1"
  }
}
```

## Why Keep `targets`

`targets` should remain even after removing `scope`.

Reasons:

- they help repair quickly localize affected graph objects
- they work across F1-F4, not only F4
- they are not equivalent to check arguments

`args` describes how a check was executed. `targets` describes which graph entities are implicated by the failure. Both are useful and should coexist.

## Query Surface For Repair

No checkpoint summary helper is needed for the minimum viable design. Repair should be able to start from `evaluation_report` and drill down directly.

Minimum repair query surface:

- `topology_view()`
- `validate()`
- `get_node(node_id)`
- `get_link(link_id)`
- `find_checkpoints(...)`
- `get_checkpoint(checkpoint_id)`
- access to grounded logical constraints, either as direct context or via `get_constraint(constraint_id)`

This supports the intended trace path:

`issue -> provenance -> checkpoint -> grounded constraint -> graph`

## Mutation Surface

### Graph Mutations

- `add_node`
- `update_node`
- `remove_node`
- `add_link`
- `update_link`
- `remove_link`

### Authored-Check Mutations

Repair also needs the ability to edit authored F4 artifacts. Final naming can be decided during implementation, but the required capability set is:

- inspect a checkpoint
- add a checkpoint
- replace or update a checkpoint
- remove a checkpoint
- replace the validator script

These tools should let repair make local corrections without re-running the full author node.

## Non-Goals

- adding a statement compiler layer
- making builder subordinate to checkpoints
- deciding final tool names for checkpoint/script mutation in this document
- redesigning the ground artifact again
