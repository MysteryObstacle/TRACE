# Fact Kinds

Logical fact kinds:

- `logical.addressing.subnet`
- `logical.addressing.interface`
- `logical.topology.direct`
- `logical.topology.chain`
- `logical.topology.ring`
- `logical.topology.star`
- `logical.topology.mesh`
- `logical.custom`

Physical fact kinds:

- `physical.image.capability`
- `physical.image.exact`
- `physical.flavor.minimum`
- `physical.flavor.exact`
- `physical.custom`

Runtime validator issue families:

- `constraint.file.*`
- `constraint.kind.unknown`
- `checkpoint.file.*`
- `checkpoint.coverage.*`
- `checkpoint.execution.*`
- `checkpoint.return.*`
- `mutation.file.*`
- `mutation.execution.*`

Use `*.custom` only when a grounded fact cannot be represented by the specific families above.
