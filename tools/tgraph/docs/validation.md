# Validation

## Purpose
Summarize layered TGraph validation from payload shape through semantic consistency.

## Accepted Input
A graph payload with `profile`, `nodes`, and `links`.

## Returned Output
A list of repair-friendly validation issues.

## Common Error Codes
- `missing_top_level_field`
- `schema_validation_error`
- `duplicate_port_id`
- `link_id_mismatch`
- `port_degree_exceeded`
- `missing_port_reference`

## Minimal Example
```json
{"profile": "logical.v1", "nodes": [], "links": []}
```

## Agent Usage Guidance
Validation is layered:

- F1 checks payload shape
- F2 checks profile-aware schema
- F3 checks semantic consistency
- F4 checks intent rules

Important semantic rules in the current model:

- `port.id` must be globally unique
- one `port` may participate in at most one `link`
- `link.id` must match the endpoint ports
- removing a linked port should fail until the link is disconnected
