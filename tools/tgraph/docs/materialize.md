# Materialize

## Purpose
Promote a logical TGraph into a physical TAAL profile by filling deployment defaults.

## Accepted Input
A `logical.v1` graph plus optional per-type default mappings.

## Returned Output
A `taal.default.v1` graph with normalized `image`, `flavor`, and link ownership fields.

## Common Error Codes
- `materialize_missing_image_mapping`
- `materialize_missing_flavor_mapping`
- `materialize_port_owner_not_found`

## Minimal Example
```json
{"profile": "taal.default.v1", "nodes": [], "links": []}
```

## Agent Usage Guidance
Use materialization in the physical stage instead of mutating logical graphs in place.
