# Repair Contract

Repair the stage artifact shape for one issue class per node invocation. The validator node runs full validation after you stop.

## Artifact shape

- `graph`
- `constraint_files`
- `checkpoint_files`

## Workflow

1. Read `evaluation_report` and inspect only what you need.
2. Apply exactly one successful change: one mutation apply or one checkpoint rewrite.
3. Stop after success. Do not validate or loop inside this node.

## Decision table

| Issue signal | Action |
|--------------|--------|
| Topology / addressing / link / CIDR on graph | write a mutation file, then `write_mutation_file` + `execute_mutation_file` |
| Image / flavor metadata on computer nodes | mutation with `set_node_image` / `set_node_flavor` |
| Checkpoint syntax, coverage, or `check_*` misuse | `write_checkpoint_file` |
| `*.escalation.*` in report | return escalation; do not mutate graph |
| `mutation.execution.exception` | fix mutation API using `docs/tgraph_editor_api.md` |

## Image selection (physical stage, tool-time only)

Use `find_images` and `get_image` while choosing images. Encode chosen ids in the mutation or checkpoint file. Never call catalog tools inside `mutate(tgraph)` or inside checkpoint functions.

## Forbidden

- `validate_graph`, `validate=true` on execute, or repair loops inside one node
- Inventing workflow, knowledge, or catalog facts inside TGraph
- Changing logical topology during physical repair unless the report requires it
