# TGraph Physical Metadata

## Physical metadata rules

- `image` must be an object with `id` and `name` when present.
- `flavor` must be an object with `vcpu`, `ram`, and `disk` when present.
- Do not emit string shorthand for `image` or `flavor`.
- Physical builder may enrich nodes with deployment metadata while preserving logical topology.
- Physical author should validate deployment-property constraints through F4 checkpoints and custom validator functions.
