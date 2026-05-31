# Repair Playbook

Repair the stage artifact shape:

- `graph`
- `constraint_files`
- `checkpoint_files`

Inspect when needed, write one mutation or checkpoint fix, execute or save it, then stop. The validator node runs full validation; do not validate or loop inside repair.

If the problem is an intent mismatch rather than a graph-structure mismatch, update the caller-owned checkpoint file instead of inventing new graph fields.

Do not invent workflow decisions inside TGraph. Do not invent knowledge, image catalog choices, flavor catalog choices, or domain facts. The caller must provide those outside TGraph.

## Image Selection

When choosing images during physical-stage repair, use the `find_images` and `get_image` agent tools. Do not recall `image_id` from memory.
