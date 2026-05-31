# Physical Author Contract

Write `physical/checkpoints.py` only. Catalog tools are for this authoring node only, not inside checkpoint functions.

## Tool-time (agent)

`image_catalog_summary`, `list_images`, `find_images`, `get_image` — use to discover canonical ids, then encode constants in the checkpoint file.

## Checkpoint runtime (allowed)

Same read/check patterns as logical checkpoints: `node`, `ports(node_id=...)`, formal `check_image_*`, `check_flavor_*`, `escalate`.

## Forbidden in checkpoint files

Catalog tools, mutation APIs, legacy helpers, invented `software` / `packages` / `zone` fields.

## Escalation kinds (physical only)

- `physical.escalation.no_satisfying_image`
- `physical.escalation.no_satisfying_flavor`
