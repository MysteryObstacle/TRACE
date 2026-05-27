# Validation

TRACE validates TGraph stage artifacts in four layers.

- F1 format: JSON object shape and required top-level fields.
- F2 schema: Pydantic schema, supported node/link fields, supported node types.
- F3 consistency: port ownership, link endpoint references, link id canonicalization, port degree, IP/CIDR consistency.
- F4 intent: file-backed constraint facts and authored checkpoint functions.

Use F1-F3 issues to repair graph structure. Use F4 issues to decide whether the graph fails grounded intent or the authored checkpoint/script is wrong.

Repair priority:

1. Fix malformed graph shape and missing references.
2. Fix topology realization, such as missing required links.
3. Fix addressing and device semantics.
4. Fix checkpoint functions that encode the wrong intent.

Do not edit validator scripts just to force a bad graph to pass.

Useful F3 reminders:

- Router ports require IPv4 addresses.
- Switch ports must not carry host IPs and must declare CIDR.
- All switch ports on one switch must share the same CIDR.
- A port may participate in at most one link.

Useful F4 reminders:

- Constraint files are JSON objects keyed by constraint id.
- Checkpoint files define one function per constraint: `check_<constraint_id>(tgraph)`.
- Prefer formal TGraph view APIs such as `tgraph.check_subnet`, `tgraph.check_direct_link`, `tgraph.check_chain`, `tgraph.check_ring`, `tgraph.check_star`, and `tgraph.check_mesh`.
- Network intent should stay CIDR-centered; do not invent `segment` or `zone` fields.
- Physical validation requires a logical reference artifact so topology preservation and required `image` / `flavor` fields can be checked.

