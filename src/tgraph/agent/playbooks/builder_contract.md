# Builder Contract

Build graph changes only through mutation files. The validator node owns full checkpoint validation.

## Workflow

1. Inspect with `inspect_graph` or `read_support_file`.
2. Write `def mutate(tgraph):` in a stage mutation file.
3. Execute with `execute_mutation_file` (apply only by default; do not pass `validate=true`).
4. If execution fails, read `docs/tgraph_editor_api.md` and correct the mutation file.
5. After one successful apply, stop. Do not call `validate_graph` or re-run full validation here.

## Logical mutation API (allowed)

- `ensure_direct_link`
- `ensure_chain`
- `ensure_subnet`
- `ensure_interface`

## Physical mutation API (allowed)

- `set_node_image`
- `set_node_flavor`

Set `image` and `flavor` on `type=computer` nodes only unless the evaluation report says otherwise.

## Forbidden inside mutation files

- `ensure_link`, `add_link`, `ensure_node`, `set_link`, `validate_graph`
- `check_*`, `node()`, `ports()`, `paths()`, `neighbors()`
- Catalog tools: `find_images`, `list_images`, `get_image`
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
