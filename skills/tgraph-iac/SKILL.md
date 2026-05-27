---
name: tgraph-iac
description: Generate, inspect, repair, validate, and export TGraph-based Infrastructure-as-Code artifacts. Use when Codex needs to work with TRACE/TGraph IR, apply controlled graph updates to logical or physical topology artifacts, validate F1-F4 constraints, repair authored constraint/checkpoint files, or export validated TGraph artifacts to IaC-oriented outputs.
---

# TGraph IaC

Use TGraph as a stable IaC intermediate representation. Work through focused inspection, mutation files, file-backed checkpoint validation, and export instead of rewriting full artifacts by hand.

## Workflow

1. Locate TRACE before using scripts. Prefer `--trace-root <TRACE repo>`; otherwise use `TGRAPH_TRACE_ROOT`, `TGRAPH_TRACE_PYTHON`, or an installed TRACE package.
2. Inspect first with `scripts/tgraph_inspect.py` to avoid loading or rewriting full artifacts.
3. Build one coherent mutation file when graph changes are needed.
4. Execute mutation files through TRACE stage tools, or edit artifacts only when the user explicitly asks for a rebuild.
5. Validate with `scripts/tgraph_validate.py`.
6. Iterate from `rejected_ops` and `validation.issues`.
7. Export only after validation passes.

## Commands

```powershell
python <skill>/scripts/tgraph_inspect.py --trace-root D:/Projects/Trace --artifact artifact.json --stage logical --query topology
python <skill>/scripts/tgraph_validate.py --trace-root D:/Projects/Trace --artifact artifact.json --stage logical --levels f1,f2,f3,f4
python <skill>/scripts/tgraph_export.py --trace-root D:/Projects/Trace --artifact artifact.json --stage logical --target tgraph-json --out ./generated
```

## Rules

- Do not directly overwrite a full artifact unless the user explicitly asks for a rebuild.
- Do not use patch-style graph updates. Use mutation files and TGraphEditor operations.
- Prefer `ensure_link` when wiring endpoints; use `ensure_port` only for deliberate dangling interfaces.
- Use `ensure_*` operations for idempotent generation and repair.
- Use `remove_*` operations only when the destructive intent is clear.
- Leave `reconnect` false unless the requested fix explicitly rewires an existing port.
- Do not repeat a rejected patch unchanged.
- TRACE stage artifacts use `graph`, `constraint_files`, and `checkpoint_files`.
- For physical validation, pass `--logical-artifact <path>` so topology preservation and required deployment metadata can be checked.
- Prefer `summary`, `cidrs`, `path`, `links`, and `support-files` inspection over full artifact dumps.

## References

- Read `references/tgraph-ir.md` when artifact shape or stage fields are unclear.
- Read `references/validation.md` when interpreting F1-F4 issues.
- Read `references/agent-workflows.md` for generation, repair, and export loops.
- Read `references/export-targets.md` before exporting.

