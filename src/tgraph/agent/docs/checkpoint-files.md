# Checkpoint Files

Checkpoint files are Python files. They are derived artifacts and may be regenerated.

Each constraint id must have exactly one function:

```python
def check_lc9(tgraph):
    return tgraph.check_chain(["WEB", "SW_DMZ", "R_CORE"])
```

Functions receive a read-only `TGraphView`. They must not mutate the graph.

Preferred one-line checks:

- `tgraph.check_subnet("SW_DMZ", "10.10.10.0/24")`
- `tgraph.check_interface("WEB", segment="SW_DMZ", cidr="10.10.10.0/24", ip="10.10.10.10")`
- `tgraph.check_direct_link("WEB", "SW_DMZ", link_key="1")`
- `tgraph.check_chain(["WEB", "SW_DMZ", "R_CORE"])`
- `tgraph.check_ring(["A", "B", "C"])`
- `tgraph.check_star(center="SW1", leaves=["PC1", "PC2"])`
- `tgraph.check_mesh(["R1", "R2", "R3"])`
- `tgraph.check_image_exact("FIREWALL", image_id="img_firewall")`
- `tgraph.check_flavor_minimum("PLC1", vcpu=1, ram=512, disk=4)`
- `tgraph.check_flavor_exact("PLC1", vcpu=1, ram=512, disk=4)`

Custom checks may return issue dictionaries:

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
                "targets": ["GUEST", "PLC1"]
            }
        }]
    return []
```

Repair-friendly issue guidance:

- Include a precise `message`.
- Include `details.issue_kind`.
- Include `details.repair_target` when obvious: `graph`, `checkpoint`, `constraint`, or `catalog`.
- Include `details.targets` for node/link/path names when useful.
