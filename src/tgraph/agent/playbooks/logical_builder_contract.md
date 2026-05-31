# Logical Builder Contract

Build logical graph topology only through one mutation file. The validator node owns full checkpoint validation.

## Workflow

1. Inspect with `inspect_graph` or read stage support files only as needed.
2. Write one `def mutate(tgraph):` in a logical stage mutation file containing the initial logical topology changes you can determine.
3. Execute with `execute_mutation_file` (apply only by default; do not pass `validate=true`).
4. If execution fails before applying, read `docs/tgraph_editor_api.md` and correct the mutation file.
5. After the first successful apply, stop. Do not call more tools, inspect, read docs, call `validate_graph`, or re-run full validation here.

A successful apply is node completion, even if the validator later finds issues.

## Logical mutation API (allowed)

- `ensure_direct_link`
- `ensure_chain`
- `ensure_subnet`
- `ensure_interface`

Prefer one complete initial topology mutation over a sequence of one-link or one-field mutation files.

## Forbidden inside logical mutation files

- Physical metadata APIs: `set_node_image`, `set_node_flavor`
- Nonexistent editor APIs: `ensure_link`, `add_link`, `ensure_node`, `set_link`
- Validation or checkpoint APIs: `validate_graph`, `check_*`
- Read-only view APIs: `node()`, `nodes()`, `port()`, `ports()`, `links()`, `paths()`, `neighbors()`
- Catalog tools: `find_images`, `list_images`, `get_image`, `image_catalog_summary`
- Legacy helpers: `get_ports`, `ip_in_subnet`, `get_node`
- Unsupported IR fields: `zone`, `firewall_rules`, `software`, `packages`

`segment` is only a parameter to `ensure_interface`, not a graph field.

## Common mistakes

```python
# Wrong — no ensure_link API
tgraph.ensure_link("WEB", "SW_DMZ")

# Right
tgraph.ensure_direct_link("WEB", "SW_DMZ")
# or
tgraph.ensure_chain(["WEB", "SW_DMZ", "R_CORE"])
```
