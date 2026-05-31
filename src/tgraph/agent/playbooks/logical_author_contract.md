# Logical Author Contract

Write `logical/checkpoints.py` only. Checkpoint functions receive only `tgraph`.

## Checkpoint runtime (allowed signatures)

- `tgraph.node(node_id)`
- `tgraph.nodes(type=...)`
- `tgraph.port(node_id, port_id)`
- `tgraph.ports(node_id=...)` — use the `node_id=` keyword; do not pass a bare positional node id
- `tgraph.links(...)`, `tgraph.neighbors(node_id)`, `tgraph.paths(...)`, `tgraph.cidrs()`, `tgraph.ip_in_cidr(ip, cidr)`
- Formal `check_*`, `tgraph.issue(...)`, `tgraph.escalate(...)`

`check_*` returns issue lists, not graph objects. Do not call `check_interface(...).get(...)`.

## Forbidden in checkpoint files

Mutation APIs (`ensure_*`, `set_*`), `validate_graph`, legacy names (`get_ports`, `ip_in_subnet`, `get_node`), catalog tools.

There is no `check_cidr` — use `check_subnet(switch, cidr)`.

## Custom issue return shape (required when not using one-line `check_*`)

Each failed check must return `[]` / `None` on pass, or one dict or a list of dicts on fail. Every dict must validate as a `ValidationIssue`:

- Top-level **`message`** (string) — not `detail`, `description`, or `kind`.
- Top-level optional **`severity`**: `"error"` or `"warning"`.
- Top-level optional **`location`** (string).
- **`details`** object with required **`issue_kind`** (string) — not a top-level `kind` field.
- Put **`repair_target`** inside **`details`**: `"graph"`, `"checkpoint"`, or `"constraint"` when obvious.

Forbidden top-level fields: `kind`, `detail`, `description`, `nodes` (use `details.targets` instead).

Template:

```python
def check_lc20(tgraph):
    if tgraph.path_exists("GUEST", "PLC1"):
        return [{
            "message": "GUEST must not reach PLC1",
            "severity": "error",
            "location": "GUEST->PLC1",
            "details": {
                "issue_kind": "logical.custom.forbidden_path_exists",
                "repair_target": "graph",
                "targets": ["GUEST", "PLC1"],
            },
        }]
    return []
```

Prefer `tgraph.issue(...)` when it matches the constraint semantics.

## Escalation kinds (logical only)

- `logical.escalation.constraint_conflict`
- `logical.escalation.no_satisfying_topology`
