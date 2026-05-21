# Agent Workflows

## Generate

1. Create a logical or physical artifact envelope.
2. Add nodes with `ensure_node`.
3. Connect topology with `ensure_link`.
4. Add grounded intent checks with `ensure_checkpoint`.
5. Validate.
6. Export.

## Repair

1. Read the current validation report.
2. Inspect only the needed graph region.
3. Decide whether the issue belongs to graph, checkpoint, or validator script.
4. Apply one coherent patch.
5. Validate.
6. Iterate only from new `rejected_ops` and `validation.issues`.

Prefer dry-run when a patch removes nodes, removes links, or uses `reconnect: true`.

## Export

1. Validate the artifact.
2. Read `export-targets.md`.
3. Run `tgraph_export.py`.
4. Treat unsupported targets as explicit `export_error`, not as permission to invent a target format.

