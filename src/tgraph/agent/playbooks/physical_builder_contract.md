# Physical Builder Contract

Set initial physical metadata through exactly one mutation file. The validator node owns full checkpoint validation.

## Workflow

1. Use catalog tools and `inspect_graph` only while choosing ids.
2. Write one `def mutate(tgraph):` containing all initial `set_node_image` / `set_node_flavor` assignments for `type=computer` nodes you can determine.
3. Execute with `execute_mutation_file` (apply only; do not pass `validate=true`).
4. If execution fails before applying, read `docs/tgraph_editor_api.md` and correct the mutation file.
5. After the first successful apply, stop. Do not call more tools.

A successful apply is node completion, even if the validator later finds issues.

## Physical mutation API (allowed)

- `set_node_image(node_id, image)` — image may be a canonical id string or `{"id": ..., "name": ...}`
- `set_node_flavor(node_id, vcpu=..., ram=..., disk=...)`

## Forbidden inside physical mutation files

- Wrong names: `set_image`, `set_flavor`, `ensure_*`, topology editors
- Catalog tools: `find_images`, `list_images`, `get_image`, `image_catalog_summary`
- Read/check APIs: `node()`, `check_*`, `validate_graph`
- Unsupported fields: `software`, `packages`, `zone`, `firewall_rules`

Do not modify logical topology. Do not set image/flavor on router or switch nodes unless the role contract says otherwise.
