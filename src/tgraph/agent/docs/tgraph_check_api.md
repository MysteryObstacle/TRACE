# TGraph Check API

Formal fact checks return issue dicts (or empty list when satisfied).

```python
tgraph.check_subnet("SW_DMZ", "10.10.10.0/24")  # not check_cidr
tgraph.check_interface("R_CORE", segment="SW_DMZ", cidr="10.10.10.0/24", ip="10.10.10.1")  # segment is required: neighboring node id (parameter, not an IR field)
tgraph.check_direct_link("WEB", "SW_DMZ")
tgraph.check_chain(["WEB", "SW_DMZ", "R_CORE"])
tgraph.check_ring(["R1", "R2", "R3", "R1"])
tgraph.check_star(center="SW_CORE", leaves=["PC1", "PC2"])
tgraph.check_mesh(["R1", "R2", "R3"])
tgraph.check_image_exact("WEB", "img_web")
tgraph.check_flavor_minimum("WEB", vcpu=2, ram=2048, disk=20)
tgraph.check_flavor_exact("WEB", vcpu=2, ram=2048, disk=20)
```

Custom facts may use helper logic and `tgraph.issue(...)`.

When ground constraints are unsatisfiable, use `tgraph.escalate(issue_kind, message, ...)` with:

- `logical.escalation.constraint_conflict`
- `logical.escalation.no_satisfying_topology`
- `physical.escalation.no_satisfying_image`
- `physical.escalation.no_satisfying_flavor`
