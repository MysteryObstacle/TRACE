# Export

## Purpose
Export canonical TGraph payloads to deterministic `logical.v1` or `taal.default.v1` JSON.

## Accepted Input
A canonical TGraph model or dict payload with `profile`, `nodes`, and `links`.

## Returned Output
A JSON-ready dict from `serialize()` or stable JSON text from `export_tgraph_json()`.

## Common Error Codes
- `unsupported_export_profile`
- `export_profile_mismatch`
- `export_non_serializable_value`

## Minimal Example
```json
{"profile": "logical.v1", "nodes": [], "links": []}
```

## Agent Usage Guidance
Use export helpers when writing runtime artifacts so stage code does not hand-roll JSON field names.
