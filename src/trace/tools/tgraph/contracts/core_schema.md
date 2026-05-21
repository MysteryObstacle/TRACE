# TGraph Core Schema

## Canonical TGraphJSON shape

- Top-level keys: `profile`, `nodes`, `links`
- Logical profile: `logical.v1`
- Physical profile: `taal.default.v1`

### Node object

- Required keys: `id`, `type`, `label`, `ports`
- Optional keys: `image`, `flavor`
- Supported `type` values: `switch`, `router`, `computer`

### Port object

- Required key: `id`
- Prompt-visible semantic keys: `ip`, `cidr`

### Link object

- Required keys: `id`, `from_port`, `to_port`
- Optional keys: `from_node`, `to_node`
- Canonical link id format after normalization: `{from_port}--{to_port}`
- Do not invent alternate link shapes such as `source/target`, `a/b`, nested endpoint objects, or `connected`
