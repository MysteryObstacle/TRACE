# Export Targets

V1 supports:

- `tgraph-json`: writes normalized TGraph JSON as `tgraph.json`.

Future targets may include:

- `terraform`
- `opentofu`
- `ansible`

Until a target is implemented by the TRACE backend, `tgraph_export.py` returns `export_error`. Do not hand-roll Terraform, OpenTofu, or Ansible output through this Skill unless the user explicitly asks for a separate manual export.

