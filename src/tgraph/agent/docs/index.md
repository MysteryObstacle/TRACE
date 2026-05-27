# TGraph Agent Docs

Use these short references when authoring checkpoints, mutations, or repairs.

| Task | Doc |
|------|-----|
| Reading / inspecting graphs | [tgraph_view_api.md](tgraph_view_api.md) |
| Writing checkpoint files | [checkpoint_authoring.md](checkpoint_authoring.md), [tgraph_check_api.md](tgraph_check_api.md), [fact_kinds.md](fact_kinds.md) |
| Writing mutation files | [mutation_authoring.md](mutation_authoring.md), [tgraph_editor_api.md](tgraph_editor_api.md) |
| Repairing from validation issues | [repair_playbook.md](repair_playbook.md) |

Constraint files live under `ground/logical_constraints.json` and `ground/physical_constraints.json`.
Checkpoint files: `logical/checkpoints.py`, `physical/checkpoints.py`.
