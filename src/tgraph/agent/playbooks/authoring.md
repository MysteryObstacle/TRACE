# Authoring Playbook

Create or update a stage artifact with:

- `graph`
- `constraint_files`
- `checkpoint_files`

Use inspect for current context, controlled mutation for graph edits, and validate after every meaningful change.

Use checkpoint files for intent checks that do not belong in the graph shape itself. Each function is named `check_<constraint_id>(tgraph)` and should normally call one of the formal `tgraph.check_*` APIs.

## Escalation (return to ground)

Use escalation issue kinds **only** when the constraint itself is wrong or mutually unsatisfiable — not when the graph is merely incomplete or misconfigured (those belong in repair).

Allowed kinds:

- `logical.escalation.constraint_conflict`
- `logical.escalation.no_satisfying_topology`
- `physical.escalation.no_satisfying_image`
- `physical.escalation.no_satisfying_flavor`

Example:

```python
def check_lc12(tgraph):
    if lc12_conflicts_with_lc15(tgraph):
        return tgraph.escalate(
            "logical.escalation.constraint_conflict",
            "lc12 ring and lc15 star cannot both hold on R1,R2,R3",
            targets=["R1", "R2", "R3"],
        )
    return tgraph.check_ring(["R1", "R2", "R3", "R1"])
```

There is no `check_cidr` API — use `check_subnet(switch, cidr)`.

Network intent must stay CIDR-centered. Do not invent segment-style IR fields.

Do not invent workflow, knowledge, catalog, image, flavor, or domain assumptions inside TGraph. Put caller-owned context in the outer application.

## TGraph Check / Editor API (interface fact authoring)

When the constraint is interface-shaped, use these APIs explicitly:

- `tgraph.check_interface(node, segment=..., cidr=None, ip=None, link_key=None)`
  - `segment` is **required**; it is the neighboring switch / segment-carrier node id (a function parameter that points to another node), not an IR field on nodes or ports.
  - `cidr`, `ip`, and `link_key` are optional refinements.
- `tgraph.ensure_interface(node, segment=..., cidr=..., ip=None, link_key=None)`
  - Same `segment` semantics. The mutation creates or updates the interface port.

`segment` always identifies an existing node id. It is never a top-level IR field.
