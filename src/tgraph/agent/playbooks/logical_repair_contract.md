# Logical Repair Contract

Select one coherent repair batch per invocation. The validator runs full validation after you stop.

## Coherent batch

A batch may include multiple issues only when they:

- share one category: graph mutation, checkpoint rewrite, logical escalation, or cannot repair;
- use one mechanism: one mutation file **or** one checkpoint rewrite, never both;
- do not need validator feedback between fixes.

Examples you may batch in one mutation: several subnet CIDR fixes, several missing links/interfaces of the same kind.

Do not mix graph mutation and checkpoint rewrite in the same invocation.

## Graph repair form

Use one semantic mutation file with idempotent `ensure_*` editor APIs. Do not write raw graph JSON patches or low-level delete/add port operations unless a documented remove API exists in the editor contract.

## Checkpoint repair form

Rewrite `logical/checkpoints.py` in one `write_checkpoint_file` call. You may fix multiple checkpoint API mistakes in that single rewrite.

## Issue routing (read `evaluation_report` first)

| `details.issue_kind` | Batch | Action |
|----------------------|-------|--------|
| `checkpoint.return.invalid` | checkpoint only | Fix the named `check_<constraint_id>` return shape (`message` + `details.issue_kind`). Do **not** run graph mutation — the graph may already be fine. |
| `checkpoint.file.*`, `checkpoint.coverage.*`, `checkpoint.execution.*` | checkpoint | Rewrite checkpoints or fix API/syntax in that file. |
| `logical.*` topology/addressing (not checkpoint meta) | graph | One mutation file with `ensure_*`. |
| `logical.escalation.*` | escalation | Do not mutate; follow escalation playbook. |

When `details.repair_target` is `checkpoint`, always choose the checkpoint batch even if the constraint statement sounds like a graph problem.

## After success

One successful mutation apply or checkpoint rewrite completes this node. Do not call more tools, read docs, or inspect the graph.

## Logical mutation API (allowed)

`ensure_direct_link`, `ensure_chain`, `ensure_subnet`, `ensure_interface`

## Forbidden

Physical metadata APIs, catalog tools, `ensure_link`, `check_*` inside mutations, `validate_graph`, legacy helpers.
