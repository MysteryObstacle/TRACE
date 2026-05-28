# TRACE Agent Tool Boundary Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore LangGraph validator ownership by preventing builder/repair agents from self-validating or looping after a successful artifact change.

**Architecture:** Make `StageRepairTools` enforce an agent-node apply gate and compact tool result contract. Remove `validate_graph` from builder/repair tool surfaces, route escalation decisions through repair, and expose agent docs through the existing support-file reader.

**Tech Stack:** Python, LangGraph, LangChain tools, pytest, TRACE `StageRepairTools`, TGraph validate/inspect/mutation APIs.

---

## Chunk 1: Tool Boundary And Apply Gate

### Task 1: Remove Agent-Facing Full Validation

**Files:**
- Modify: `src/trace/stages/repair_tools.py`
- Modify: `src/trace/stages/logical/prompts/builder.md`
- Modify: `src/trace/stages/logical/prompts/repair.md`
- Modify: `src/trace/stages/physical/prompts/builder.md`
- Modify: `src/trace/stages/physical/prompts/repair.md`
- Test: `tests/unit/stages/test_repair_tools_boundary.py`
- Test: `tests/unit/config/test_prompts.py`

- [ ] **Step 1: Write failing tests**

Assert builder/repair tool lists do not include `validate_graph` by default. Assert prompts no longer instruct agents to call `validate_graph`.

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
pytest -q tests/unit/stages/test_repair_tools_boundary.py tests/unit/config/test_prompts.py
```

- [ ] **Step 3: Implement the tool surface split**

Add an `include_validate_tool: bool = False` parameter to `StageRepairTools.as_agent_tools(...)`. Keep validator internals using `StageRepairTools.validate_graph()` as a normal Python method, but do not expose it to builder/repair agents.

- [ ] **Step 4: Update prompts**

Replace “Call `validate_graph` after repair actions” with “after one successful apply or checkpoint write, stop and return; validator will run full checks.”

- [ ] **Step 5: Verify**

Run the tests above and expect PASS.

### Task 2: Default Mutation Execution To Apply-Only

**Files:**
- Modify: `src/trace/stages/repair_tools.py`
- Modify: `src/tgraph/operations/mutate/scripts.py` only if low-level default must also change
- Test: `tests/unit/stages/test_repair_tools_boundary.py`
- Test: `tests/unit/tgraph/operations/test_mutation_scripts.py`

- [ ] **Step 1: Write failing tests**

Assert the agent tool schema/default uses `validate=false`. Assert `StageRepairTools.execute_mutation_file(path=...)` does not run checkpoint/F4 unless requested.

- [ ] **Step 2: Implement default**

Change `_ExecuteMutationFileInput.run_validate` to default `False`. Keep explicit `validate=true` supported for non-agent tests/debug, but prompts should not recommend it.

- [ ] **Step 3: Verify**

Run:

```powershell
pytest -q tests/unit/stages/test_repair_tools_boundary.py tests/unit/tgraph/operations/test_mutation_scripts.py
```

### Task 3: Enforce One Successful Change Per Node

**Files:**
- Modify: `src/trace/stages/repair_tools.py`
- Test: `tests/unit/stages/test_repair_tools_boundary.py`

- [ ] **Step 1: Write failing tests**

Test that failed `execute_mutation_file` attempts allow another write/execute. Test that after a successful execute, later `write_mutation_file`, `execute_mutation_file`, and `write_checkpoint_file` return `{ok:false, error}` instructing the agent to return.

Also test checkpoint-only repair: once `write_checkpoint_file` succeeds, later mutation/checkpoint writes are rejected.

- [ ] **Step 2: Implement gate**

Track `self._successful_change_applied: bool`. Set it after successful mutation apply and after successful checkpoint write. Before mutating tools run, return a compact error if the gate is closed.

- [ ] **Step 3: Verify**

Run:

```powershell
pytest -q tests/unit/stages/test_repair_tools_boundary.py
```

## Chunk 2: Compact Results And Recoverable Tool Errors

### Task 4: Slim Mutation Tool Return

**Files:**
- Modify: `src/trace/stages/repair_tools.py`
- Test: `tests/unit/stages/test_repair_tools_summary.py`
- Test: `tests/unit/stages/test_produced_files.py`

- [ ] **Step 1: Write failing tests**

Assert default mutation result does not include `operations`. Assert `include_operations=true` includes them for debugging. Assert failure payload includes issues and summary but not the full successful operation list.

- [ ] **Step 2: Implement result contract**

Add `include_operations: bool = False` to the tool input and method. Default payload: `ok`, `path`, `applied`, `summary`, optional `issues`. Keep full graph behind `include_graph=true`.

- [ ] **Step 3: Verify**

Run:

```powershell
pytest -q tests/unit/stages/test_repair_tools_summary.py tests/unit/stages/test_produced_files.py
```

### Task 5: Contain Inspect Errors

**Files:**
- Modify: `src/trace/stages/repair_tools.py`
- Optionally modify: `src/tgraph/operations/inspect/__init__.py`
- Test: `tests/unit/stages/test_repair_tools_summary.py`

- [ ] **Step 1: Write failing tests**

Assert `tools.inspect_graph(view="nodes")` returns `{ok:false, allowed_views:[...]}` or a supported node-list response, and does not raise.

- [ ] **Step 2: Implement**

Prefer tool-layer containment in `StageRepairTools.inspect_graph`. Optionally alias `nodes` to a compact list if useful.

- [ ] **Step 3: Verify**

Run:

```powershell
pytest -q tests/unit/stages/test_repair_tools_summary.py
```

## Chunk 3: Docs Access And API Drift

### Task 6: Read Agent Docs Through Support Reader

**Files:**
- Modify: `src/trace/stages/repair_tools.py`
- Test: `tests/unit/stages/test_filtered_read_tools.py`
- Test: `tests/unit/tgraph/agent/test_agent_docs.py`

- [ ] **Step 1: Write failing tests**

Assert `list_support_files()` includes an `agent_docs` group. Assert `read_support_file("docs/tgraph_view_api.md")` and `read_support_file("tgraph_view_api.md")` work. Assert docs are read-only.

- [ ] **Step 2: Implement**

Load docs from `src/tgraph/agent/docs`. Preserve filtering options `match`, `keys`, and `head_lines`.

- [ ] **Step 3: Verify**

Run:

```powershell
pytest -q tests/unit/stages/test_filtered_read_tools.py tests/unit/tgraph/agent/test_agent_docs.py
```

### Task 7: Align TGraphView Docs And Helpers

**Files:**
- Modify: `src/tgraph/agent/docs/tgraph_view_api.md`
- Modify: `src/tgraph/agent/docs/tgraph_check_api.md`
- Optionally modify: `src/tgraph/operations/validate/view.py`
- Test: `tests/unit/tgraph/agent/test_agent_docs.py`
- Test: `tests/unit/tgraph/operations/test_validate_f4.py`

- [ ] **Step 1: Write failing docs tests**

Assert docs do not mention unsupported `get_ports` or `ip_in_subnet`. Assert they document `ports(...)`, `ip_in_cidr(...)`, and that `check_interface(...)` returns a list of issues.

- [ ] **Step 2: Implement docs/helper alignment**

Prefer docs fixes. Add backward-compatible helper aliases only if demo evidence shows models keep reaching for old names despite docs.

- [ ] **Step 3: Verify**

Run:

```powershell
pytest -q tests/unit/tgraph/agent/test_agent_docs.py tests/unit/tgraph/operations/test_validate_f4.py
```

## Chunk 4: Validator And Escalation Routing

### Task 8: Remove Validator-To-Escalate Decision

**Files:**
- Modify: `src/trace/stages/logical/nodes/validator.py`
- Modify: `src/trace/stages/physical/nodes/validator.py`
- Modify: `src/trace/stages/logical/nodes/repair.py`
- Modify: `src/trace/stages/physical/nodes/repair.py`
- Test: `tests/unit/runtime/test_escalation_routing.py`
- Test: `tests/integration/test_escalation_loop.py`

- [ ] **Step 1: Write failing tests**

Assert validator routes escalation-shaped issues to repair, not directly to escalate. Assert repair can explicitly return a stage escalation when the agent produces an escalation issue/report.

- [ ] **Step 2: Implement**

Keep validator as a checker/router to repair/finalize/fail. Move stage escalation decision into repair node output handling.

- [ ] **Step 3: Verify**

Run:

```powershell
pytest -q tests/unit/runtime/test_escalation_routing.py tests/integration/test_escalation_loop.py
```

## Chunk 5: End-To-End Verification

### Task 9: Regression Suite And Demo Smoke

**Files:**
- No production files unless failures reveal gaps.

- [ ] **Step 1: Run full tests**

Run:

```powershell
pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run demo smoke**

Run:

```powershell
trace run tests/demo/demo.md --output-root runs --run-id demo-009
```

Expected: physical stage no longer crashes on `inspect_graph(view="nodes")`; traces show builder/repair returns after one successful artifact change and validator performs full checks.

- [ ] **Step 3: Inspect run artifacts**

Check:

```powershell
Get-Content runs/demo-009/run.json
Get-Content runs/demo-009/logical/repair_history.json
Get-Content runs/demo-009/physical/evaluation.json
```

Expected: no large default operation dumps, useful ledger summaries, and no agent-side full validation loop.
