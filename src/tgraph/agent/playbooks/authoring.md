# Authoring Playbook

Create or update a stage artifact with:

- `graph`
- `constraint_files`
- `checkpoint_files`

Use inspect for current context, controlled mutation for graph edits, and validate after every meaningful change.

Use checkpoint files for intent checks that do not belong in the graph shape itself. Each function is named `check_<constraint_id>(tgraph)` and should normally call one of the formal `tgraph.check_*` APIs.

Network intent must stay CIDR-centered. Do not invent segment-style IR fields.

Do not invent workflow, knowledge, catalog, image, flavor, or domain assumptions inside TGraph. Put caller-owned context in the outer application.
