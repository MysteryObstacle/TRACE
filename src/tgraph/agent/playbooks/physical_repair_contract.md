# Physical Repair Contract

Select one coherent repair batch per invocation. Preserve logical topology unless the report explicitly requires otherwise.

## Coherent batch

Categories: image metadata mutation, flavor metadata mutation, checkpoint rewrite, physical escalation, or cannot repair.

You may batch multiple image assignments, multiple flavor assignments, or image+flavor together in one mutation when they are same-direction metadata fixes and do not require re-querying the catalog between each node.

Do not mix metadata mutation and checkpoint rewrite in the same invocation.

## Metadata repair form

One semantic mutation file with `set_node_image` / `set_node_flavor` only. Use catalog tools at agent tool-time, then literals in the mutation file.

## Forbidden in mutation/checkpoint files

`set_image`, `set_flavor`, `ensure_*`, catalog tools, topology changes by default, `software`, `packages`, `zone`.

## After success

One successful mutation apply or checkpoint rewrite completes this node. Do not call more tools.
