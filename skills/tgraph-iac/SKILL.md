---
name: tgraph-iac
description: Generate, inspect, repair, validate, and export TGraph-based Infrastructure-as-Code artifacts. Use when Codex needs to work with TRACE/TGraph IR, apply declarative batch patches to logical or physical topology artifacts, validate F1-F4 constraints, repair authored checkpoints or validator scripts, or export validated TGraph artifacts to IaC-oriented outputs.
---

# TGraph IaC

Use TGraph as a stable IaC intermediate representation. Work through focused inspection, declarative batch patches, validation, and export instead of rewriting full artifacts by hand.

## Workflow

1. Locate TRACE before using scripts. Prefer `--trace-root <TRACE repo>`; otherwise use `TGRAPH_TRACE_ROOT`, `TGRAPH_TRACE_PYTHON`, or an installed TRACE package.
2. Inspect first with `scripts/tgraph_inspect.py` to avoid loading or rewriting full artifacts.
3. Build one coherent batch patch.
4. Apply changes only through `scripts/tgraph_apply_patch.py`.
5. Validate with `scripts/tgraph_validate.py`.
6. Iterate from `rejected_ops` and `validation.issues`.
7. Export only after validation passes.

## Commands

```powershell
python <skill>/scripts/tgraph_inspect.py --trace-root D:/Projects/Trace --artifact artifact.json --stage logical --query topology
python <skill>/scripts/tgraph_apply_patch.py --trace-root D:/Projects/Trace --artifact artifact.json --patch patch.json --stage logical --out artifact.json
python <skill>/scripts/tgraph_validate.py --trace-root D:/Projects/Trace --artifact artifact.json --stage logical --levels f1,f2,f3,f4
python <skill>/scripts/tgraph_export.py --trace-root D:/Projects/Trace --artifact artifact.json --stage logical --target tgraph-json --out ./generated
```

## Rules

- Do not directly overwrite a full artifact unless the user explicitly asks for a rebuild.
- Do not use RFC JSON Patch paths. Use `graph_patch`, `checkpoint_patch`, and `validator_patch`.
- Create ports only through `ensure_link`.
- Use `ensure_*` operations for idempotent generation and repair.
- Use `remove_*` operations only when the destructive intent is clear.
- Leave `reconnect` false unless the requested fix explicitly rewires an existing port.
- Before editing a validator script, confirm the issue is faulty check logic rather than a graph that fails intent.
- Do not repeat a rejected patch unchanged.

## References

- Read `references/patch-protocol.md` before authoring non-trivial patches.
- Read `references/tgraph-ir.md` when artifact shape or stage fields are unclear.
- Read `references/validation.md` when interpreting F1-F4 issues.
- Read `references/agent-workflows.md` for generation, repair, and export loops.
- Read `references/export-targets.md` before exporting.

