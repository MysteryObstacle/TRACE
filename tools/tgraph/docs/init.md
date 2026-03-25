# Init

## Purpose
Describe how external inputs are loaded into the canonical TGraph model.

## Accepted Input
Filesystem paths or JSON text passed through `load_tgraph()` and format-specific loaders.

## Returned Output
A canonical `TGraph` model.

## Common Error Codes
- `unsupported_import_format`
- `import_not_implemented`
- `import_parse_error`

## Minimal Example
```json
{"profile": "logical.v1", "nodes": [], "links": []}
```

## Agent Usage Guidance
Prefer JSON import today; `.gml` and `.gns3` are explicit stubs until later slices land.
