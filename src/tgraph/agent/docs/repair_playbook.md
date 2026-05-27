# Repair Playbook

1. Read `evaluation_report` issues; use `details.issue_kind` and `details.repair_target`.
2. `repair_target=graph` → write `logical/mutations/attempt_N.py` with editor `ensure_*` calls.
3. `repair_target=metadata` → mutation setting image/flavor on nodes.
4. `repair_target=checkpoint` → fix `logical/checkpoints.py` or `physical/checkpoints.py`.
5. `repair_target=constraint` → only when explicitly allowed; do not edit ground constraints by default.

After writing a mutation file, call `execute_mutation_file` and re-run `validate_graph`.
