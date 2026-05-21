# Validation

TRACE validates TGraph artifacts in four layers.

- F1 format: JSON object shape and required top-level fields.
- F2 schema: Pydantic schema, supported node/link fields, supported node types.
- F3 consistency: port ownership, link endpoint references, link id canonicalization, port degree, IP/CIDR consistency.
- F4 intent: authored checkpoints and optional custom validator script.

Use F1-F3 issues to repair graph structure. Use F4 issues to decide whether the graph fails grounded intent or the authored checkpoint/script is wrong.

Repair priority:

1. Fix malformed graph shape and missing references.
2. Fix topology realization, such as missing required links.
3. Fix addressing and device semantics.
4. Fix checkpoints that encode the wrong intent.
5. Fix validator script only when the check implementation is wrong.

Do not edit validator scripts just to force a bad graph to pass.

Useful F3 reminders:

- Router ports require IPv4 addresses.
- Switch ports must not carry host IPs and must declare CIDR.
- All switch ports on one switch must share the same CIDR.
- A port may participate in at most one link.

