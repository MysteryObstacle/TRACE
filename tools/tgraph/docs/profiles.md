# Profiles

## Purpose
Explain the supported JSON profiles for TRACE TGraph payloads.

## Accepted Input
Profile names embedded in graph payloads.

## Returned Output
A clear contract for `logical.v1` and `taal.default.v1`.

## Common Error Codes
- `unsupported_profile`
- `computer_image_required`
- `computer_flavor_required`
- `non_computer_image_forbidden`
- `non_computer_flavor_forbidden`

## Minimal Example
```json
{"profile": "taal.default.v1", "nodes": [], "links": []}
```

## Agent Usage Guidance
Use:

- `logical.v1` for logical stage outputs
- `taal.default.v1` for physical stage outputs

Profile choice does not change the canonical `Node`/`Port`/`Link` structure.
It changes which fields are required and how strict validation should be.
