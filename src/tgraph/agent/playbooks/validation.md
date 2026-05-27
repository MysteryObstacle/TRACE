# Validation Playbook

Run validate on the full stage artifact inputs:

- `graph`
- `constraint_files`
- `checkpoint_files`

Checkpoint functions run against read-only `TGraphView` and return issue dictionaries. The validator enriches issues with constraint id, fact kind, statement, function name, and checkpoint path.

Use inspect to focus on reported nodes, ports, links, paths, or CIDRs. Use a mutation file only when the issue belongs to the IR. Otherwise adjust the relevant checkpoint file.

Do not invent workflow fixes, knowledge, catalog entries, image choices, or domain intent while resolving validation issues.
