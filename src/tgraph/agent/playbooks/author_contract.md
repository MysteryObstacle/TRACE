# Author Contract

Write checkpoint files only. Do not build graphs or run full stage validation in this node.

## Artifact shape

- `constraint_files`
- `checkpoint_files`

Use `read_constraint_file`, `write_checkpoint_file`, and `validate_checkpoint_file` for the stage checkpoint file.

## Checkpoint functions

Each constraint id needs `check_<constraint_id>(tgraph)` in `logical/checkpoints.py` or `physical/checkpoints.py`.

- Return `[]` or `None` when satisfied.
- Return repair-friendly issue dicts when not satisfied.
- Prefer one-line `tgraph.check_*` calls for formal fact kinds.
- Use `tgraph.escalate(...)` only when the constraint itself is unsatisfiable.

## Escalation kinds

- `logical.escalation.constraint_conflict`
- `logical.escalation.no_satisfying_topology`
- `physical.escalation.no_satisfying_image`
- `physical.escalation.no_satisfying_flavor`

There is no `check_cidr` API — use `check_subnet(switch, cidr)`.

## Interface facts

- `tgraph.check_interface(node, segment=..., cidr=None, ip=None, link_key=None)`
  - `segment` is required; it is the neighboring switch node id (a parameter, not an IR field).
  - `check_interface(...)` returns a list of issues, not a port dict.
- Read port `ip` / `cidr` with `tgraph.ports(...)` or `tgraph.node(...)`, not via `check_interface`.

`segment` always identifies an existing node id.

## Checkpoint runtime API (allowed)

`node`, `nodes`, `port`, `ports`, `links`, `neighbors`, `paths`, `cidrs`, `ip_in_cidr`, formal `check_*`, `issue`, `escalate`.

## Forbidden inside checkpoint files

`ensure_*`, `set_*`, `validate_graph`, `get_ports`, `ip_in_subnet`, `get_node`, agent catalog tools (`find_images`, `list_images`, `get_image`).
