# Fact Kinds

Logical:
- `logical.addressing.subnet`
- `logical.addressing.interface`
- `logical.topology.direct`
- `logical.topology.chain`
- `logical.topology.ring`
- `logical.topology.star`
- `logical.topology.mesh`
- `logical.custom`

Physical:
- `physical.image.capability`
- `physical.image.exact`
- `physical.flavor.minimum`
- `physical.flavor.exact`
- `physical.custom`

Constraint files are JSON objects keyed by constraint id:

```json
{
  "lc1": {
    "kind": "logical.topology.chain",
    "statement": "explicit chain WEB -> SW_DMZ -> R_CORE."
  }
}
```
