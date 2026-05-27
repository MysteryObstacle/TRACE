# Repair Playbook

Repair the stage artifact shape:

- `graph`
- `constraint_files`
- `checkpoint_files`

Use the loop: inspect the graph, write a mutation file, execute it transactionally, validate, then repeat.

If the problem is an intent mismatch rather than a graph-structure mismatch, update the caller-owned checkpoint file instead of inventing new graph fields.

Do not invent workflow decisions inside TGraph. Do not invent knowledge, image catalog choices, flavor catalog choices, or domain facts. The caller must provide those outside TGraph.
