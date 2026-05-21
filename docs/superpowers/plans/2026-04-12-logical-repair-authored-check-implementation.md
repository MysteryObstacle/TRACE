# Logical Repair Authored-Check Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a one-shot migration that makes validation issues provenance-aware, upgrades logical repair to repair the full logical artifact, and adds the missing `update_link` graph mutation tool.

**Architecture:** Apply a compatibility-breaking migration across the shared TGraph validator/runtime/protocol stack first, then update logical-stage orchestration to use the new issue shape and authored-check mutation tools. Keep grounded constraints as the builder's main realization input, centralize F4 provenance stamping inside `f4_intent`, and make `BoundTGraphTools` the single mutation surface for both graph edits and logical authored-check edits.

**Tech Stack:** Python 3, Pydantic v2, LangChain tools, pytest

---

## Hard Constraints

- No backward-compatibility shims.
- Remove `scope` from active code, contracts, prompts, and tests in one pass.
- Do not keep dual parsing paths such as `code.startswith("checkpoint_")`.
- Do not keep alias tool names or dual helper signatures.
- Do not accept legacy custom-script calls like `issue(code, message, scope, ...)`; migrate all custom-script examples and tests to the new helper shape.

## File Map

**Create**

- `tests/unit/tools/tgraph/test_validation_issues.py`
  - Focused tests for `ValidationIssue`, `IssueProvenance`, F4 provenance enrichment, and script-level load failures.
- `tests/unit/stages/logical/test_logical_validator_node.py`
  - Regression tests for logical validator routing under the new provenance-based behavior.

**Modify**

- `src/trace/tools/tgraph/validate/types.py`
  - Define the new validation issue schema and provenance model; remove `scope`.
- `src/trace/tools/tgraph/validate/issues.py`
  - Replace the legacy helper signature with the new provenance-aware helper.
- `src/trace/tools/tgraph/validate/f1_format.py`
  - Emit issues without `scope`.
- `src/trace/tools/tgraph/validate/f2_schema.py`
  - Emit issues without `scope`; delete `_scope_for_location`.
- `src/trace/tools/tgraph/validate/f3_consistency.py`
  - Emit issues without `scope`.
- `src/trace/tools/tgraph/validate/f4_intent.py`
  - Centralize F4 provenance stamping for SDK checks, custom checks, unresolved functions, and validator-script load failures.
- `src/trace/tools/tgraph/validate/intent_sdk.py`
  - Continue returning plain issues, but migrate helper usage to the new signature.
- `src/trace/tools/tgraph/runtime.py`
  - Remove `scope` from runtime errors and add `update_link` runtime entrypoint.
- `src/trace/tools/tgraph/transaction.py`
  - Implement transactional `update_link`; migrate validator error creation to the new issue shape.
- `src/trace/tools/tgraph/protocol.py`
  - Expose `update_link`; add authored-check mutation tools and full artifact export/writeback helpers.
- `src/trace/tools/tgraph/contract.md`
  - Document the new issue shape and tool surface.
- `src/trace/tools/tgraph/prompting.py`
  - No logic change expected, but verify contract parsing still picks up the new tool docs.
- `src/trace/stages/logical/nodes/validator.py`
  - Route authored-check failures through repair instead of failing fast.
- `src/trace/stages/physical/nodes/validator.py`
  - Stop using `scope` and checkpoint-code prefix heuristics; read provenance explicitly.
- `src/trace/stages/logical/nodes/repair.py`
  - Pass grounded logical constraints into repair context, consume provenance-rich evaluation reports, and write back mutated checkpoints/script as part of `draft_artifact`.
- `src/trace/stages/logical/prompts/repair.md`
  - Update repair instructions to allow graph edits plus authored-check/script edits.
- `tests/unit/tools/tgraph/test_graph_core.py`
  - Cover `update_link`, new tool exposure, and custom-script helper signature changes.
- `tests/unit/stages/logical/test_repair_node.py`
  - Update fixtures away from `scope`; add repair-node coverage for authored-check/script writeback and provenance-driven targeting.
- `tests/unit/stages/physical/test_physical_validator_node.py`
  - Migrate assertions to provenance-driven authored-check failure routing.

## Chunk 1: Validation Issue Shape Migration

### Task 1: Add failing tests for the new issue and provenance model

**Files:**
- Create: `tests/unit/tools/tgraph/test_validation_issues.py`
- Modify: `src/trace/tools/tgraph/validate/types.py`
- Modify: `src/trace/tools/tgraph/validate/issues.py`

- [ ] **Step 1: Write the failing tests**

```python
from trace.tools.tgraph.validate.types import ValidationIssue
from trace.tools.tgraph.validate.issues import issue


def test_validation_issue_accepts_provenance_and_has_no_scope():
    item = ValidationIssue.model_validate(
        {
            "code": "missing_required_link",
            "message": "A is not directly connected to B",
            "severity": "error",
            "targets": ["A", "B"],
            "json_paths": [],
            "provenance": {
                "layer": "f4",
                "source": "authored_check",
                "check_id": "cp1",
                "constraint_ids": ["lc1"],
                "func": "connect_nodes",
                "impl_source": "sdk",
                "args": {"node_a": "A", "node_b": "B"},
            },
        }
    )
    assert item.provenance.check_id == "cp1"
    assert not hasattr(item, "scope")


def test_issue_helper_emits_shape_without_scope():
    payload = issue(
        "runtime_error",
        "boom",
        targets=["node:r1"],
        provenance={"layer": "f3", "source": "builtin"},
    )
    assert "scope" not in payload
    assert payload["provenance"]["layer"] == "f3"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/unit/tools/tgraph/test_validation_issues.py -q`

Expected: FAIL because `ValidationIssue` does not yet define `provenance` and `issue()` still requires `scope`.

- [ ] **Step 3: Implement the new issue models and helper**

```python
class IssueProvenance(BaseModel):
    layer: Literal["f1", "f2", "f3", "f4"]
    source: Literal["builtin", "authored_check"]
    check_id: str | None = None
    constraint_ids: list[str] = Field(default_factory=list)
    func: str | None = None
    impl_source: Literal["sdk", "custom", "unknown"] | None = None
    args: dict[str, Any] | None = None
    artifact: str | None = None


class ValidationIssue(BaseModel):
    code: str
    message: str
    severity: Literal["error", "warning"]
    targets: list[str] = Field(default_factory=list)
    json_paths: list[str] = Field(default_factory=list)
    provenance: IssueProvenance | None = None


def issue(code: str, message: str, *, severity: str = "error", targets=None, json_paths=None, provenance=None) -> dict[str, Any]:
    ...
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/unit/tools/tgraph/test_validation_issues.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/unit/tools/tgraph/test_validation_issues.py src/trace/tools/tgraph/validate/types.py src/trace/tools/tgraph/validate/issues.py
git commit -m "refactor: migrate validation issues to provenance model"
```

### Task 2: Make all validators emit the new issue shape and enrich F4 provenance

**Files:**
- Modify: `src/trace/tools/tgraph/validate/f1_format.py`
- Modify: `src/trace/tools/tgraph/validate/f2_schema.py`
- Modify: `src/trace/tools/tgraph/validate/f3_consistency.py`
- Modify: `src/trace/tools/tgraph/validate/f4_intent.py`
- Modify: `src/trace/tools/tgraph/validate/intent_sdk.py`
- Modify: `src/trace/tools/tgraph/contract.md`
- Modify: `tests/unit/tools/tgraph/test_validation_issues.py`
- Modify: `tests/unit/tools/tgraph/test_graph_core.py`

- [ ] **Step 1: Extend the failing tests for F4 provenance**

```python
def test_f4_sdk_failure_includes_checkpoint_provenance():
    ...
    assert issue["provenance"] == {
        "layer": "f4",
        "source": "authored_check",
        "check_id": "cp1",
        "constraint_ids": ["lc1"],
        "func": "connect_nodes",
        "impl_source": "sdk",
        "args": {"node_a": "A", "node_b": "B"},
    }


def test_f4_script_load_failure_points_to_validator_script_artifact():
    ...
    assert issue["provenance"]["artifact"] == "logical_validator_script"
    assert issue["provenance"]["impl_source"] == "custom"


def test_f4_unknown_function_marks_impl_source_unknown():
    ...
    assert issue["provenance"]["impl_source"] == "unknown"
```

- [ ] **Step 2: Run the focused validator tests and verify they fail**

Run: `pytest tests/unit/tools/tgraph/test_validation_issues.py tests/unit/tools/tgraph/test_graph_core.py -k "f4 or custom_script" -q`

Expected: FAIL because F4 issues currently return `scope`, omit provenance, and script-load failures do not identify the authored artifact.

- [ ] **Step 3: Implement validator migration in one pass**

```python
def _f4_provenance(*, checkpoint, func_name, impl_source, args, artifact=None) -> dict[str, Any]:
    return {
        "layer": "f4",
        "source": "authored_check",
        "check_id": checkpoint.get("id"),
        "constraint_ids": list(checkpoint.get("constraint_ids") or []),
        "func": func_name or None,
        "impl_source": impl_source,
        "args": dict(args or {}) if args is not None else None,
        "artifact": artifact,
    }
```

Implementation notes:
- Delete `_scope_for_location` from `f2_schema.py`.
- Keep `intent_sdk.py` simple; do not teach SDK functions about provenance.
- In `f4_intent.py`, normalize all checkpoint outputs, then stamp authoritative provenance there.
- Overwrite any custom-script `provenance` payloads rather than trusting script-authored provenance.
- Update `contract.md` so custom script examples use the new `issue()` helper signature with no `scope`.

- [ ] **Step 4: Re-run the focused validator tests**

Run: `pytest tests/unit/tools/tgraph/test_validation_issues.py tests/unit/tools/tgraph/test_graph_core.py -k "f4 or custom_script" -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/trace/tools/tgraph/validate/f1_format.py src/trace/tools/tgraph/validate/f2_schema.py src/trace/tools/tgraph/validate/f3_consistency.py src/trace/tools/tgraph/validate/f4_intent.py src/trace/tools/tgraph/validate/intent_sdk.py src/trace/tools/tgraph/contract.md tests/unit/tools/tgraph/test_validation_issues.py tests/unit/tools/tgraph/test_graph_core.py
git commit -m "refactor: add provenance-rich validator issues"
```

### Task 3: Update stage consumers to use provenance instead of `scope` or checkpoint-code prefixes

**Files:**
- Create: `tests/unit/stages/logical/test_logical_validator_node.py`
- Modify: `src/trace/stages/logical/nodes/validator.py`
- Modify: `src/trace/stages/physical/nodes/validator.py`
- Modify: `tests/unit/stages/physical/test_physical_validator_node.py`
- Modify: `tests/unit/stages/logical/test_repair_node.py`

- [ ] **Step 1: Write failing stage-routing tests**

```python
def test_logical_validator_routes_f4_authored_check_failures_to_repair():
    ...
    assert result["next_action"] == "repair"


def test_physical_validator_still_fails_fast_on_f4_authored_check_failures():
    ...
    assert result["next_action"] == "failed"
```

- [ ] **Step 2: Run the stage tests and verify they fail**

Run: `pytest tests/unit/stages/logical/test_logical_validator_node.py tests/unit/stages/physical/test_physical_validator_node.py -q`

Expected: FAIL because logical validator still fails fast on checkpoint-prefixed codes and physical validator still inspects `code.startswith("checkpoint_")`.

- [ ] **Step 3: Implement provenance-based routing**

```python
def _is_authored_check_issue(issue: dict[str, Any]) -> bool:
    provenance = issue.get("provenance") or {}
    return provenance.get("layer") == "f4" and provenance.get("source") == "authored_check"
```

Implementation notes:
- Logical stage: authored-check issues now go to repair, not immediate failure.
- Physical stage: keep the existing fail-fast behavior for authored-check failures, but detect them from provenance rather than code-prefix heuristics.
- Remove all remaining `scope` references from active stage tests and fixtures.

- [ ] **Step 4: Re-run the stage tests**

Run: `pytest tests/unit/stages/logical/test_logical_validator_node.py tests/unit/stages/physical/test_physical_validator_node.py tests/unit/stages/logical/test_repair_node.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/unit/stages/logical/test_logical_validator_node.py src/trace/stages/logical/nodes/validator.py src/trace/stages/physical/nodes/validator.py tests/unit/stages/physical/test_physical_validator_node.py tests/unit/stages/logical/test_repair_node.py
git commit -m "refactor: route stage validation from issue provenance"
```

## Chunk 2: Add `update_link` Across Transaction, Runtime, and Tool Protocol

### Task 4: Add failing tests for `update_link`

**Files:**
- Modify: `tests/unit/tools/tgraph/test_graph_core.py`
- Modify: `src/trace/tools/tgraph/transaction.py`
- Modify: `src/trace/tools/tgraph/runtime.py`
- Modify: `src/trace/tools/tgraph/protocol.py`
- Modify: `src/trace/tools/tgraph/contract.md`

- [ ] **Step 1: Write failing `update_link` tests**

```python
def test_transaction_update_link_rewires_existing_link_and_normalizes_id():
    ...
    tx.update_link(
        "r1:p1--r2:p1",
        from_port="r1:p2",
        to_port="r2:p3",
        from_node="r1",
        to_node="r2",
        from_ip="10.0.0.5",
        from_cidr="10.0.0.4/30",
        to_ip="10.0.0.6",
        to_cidr="10.0.0.4/30",
    )
    assert runtime.to_json()["links"][0]["id"] == "r1:p2--r2:p3"


def test_bound_tgraph_tools_expose_update_link():
    tool_names = {tool.name for tool in tools.tools()}
    assert "update_link" in tool_names
```

- [ ] **Step 2: Run the focused graph-core tests and verify they fail**

Run: `pytest tests/unit/tools/tgraph/test_graph_core.py -k "update_link or tool_surface" -q`

Expected: FAIL because `update_link` does not exist in transaction/runtime/protocol or contract docs.

- [ ] **Step 3: Implement `update_link` end-to-end**

```python
def update_link(
    self,
    link_id: str,
    *,
    from_port: str | None = None,
    to_port: str | None = None,
    from_node: str | None = None,
    to_node: str | None = None,
    from_ip: str | None = None,
    from_cidr: str | None = None,
    to_ip: str | None = None,
    to_cidr: str | None = None,
) -> dict[str, Any]:
    ...
```

Implementation notes:
- Treat `update_link` as an atomic mutation, not `remove_link + add_link` exposed to the agent.
- Normalize the final link id from the final endpoint ports.
- Reuse the existing add-link logic for port materialization and endpoint addressing where practical, but do not keep alias wrappers.
- Update `contract.md` so `prompting.py` can expose a real description for `update_link`.

- [ ] **Step 4: Re-run the graph-core tests**

Run: `pytest tests/unit/tools/tgraph/test_graph_core.py -k "update_link or tool_surface" -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/unit/tools/tgraph/test_graph_core.py src/trace/tools/tgraph/transaction.py src/trace/tools/tgraph/runtime.py src/trace/tools/tgraph/protocol.py src/trace/tools/tgraph/contract.md
git commit -m "feat: add update_link mutation tool"
```

## Chunk 3: Upgrade Logical Repair to Repair the Full Logical Artifact

### Task 5: Add failing tests for authored-check and validator-script mutations

**Files:**
- Modify: `tests/unit/tools/tgraph/test_graph_core.py`
- Modify: `src/trace/tools/tgraph/protocol.py`

- [ ] **Step 1: Write failing authored-check mutation tests**

```python
def test_bound_tgraph_tools_can_add_update_and_remove_checkpoint():
    ...
    tools.add_checkpoint({...})
    tools.update_checkpoint("cp1", description="patched", args={"node_a": "A", "node_b": "B"})
    tools.remove_checkpoint("cp1")


def test_bound_tgraph_tools_can_replace_validator_script_and_validate_against_it():
    ...
    tools.replace_validator_script("def check_rule(tgraph, **kwargs):\\n    return []\\n")
    assert tools.validate()["ok"] is True
```

- [ ] **Step 2: Run the focused tool tests and verify they fail**

Run: `pytest tests/unit/tools/tgraph/test_graph_core.py -k "checkpoint or validator_script" -q`

Expected: FAIL because `BoundTGraphTools` currently exposes checkpoints as read-only metadata and cannot mutate or export the authored artifact.

- [ ] **Step 3: Implement authored-check mutation tools in `BoundTGraphTools`**

```python
def add_checkpoint(self, checkpoint: dict[str, Any]) -> dict[str, Any]: ...
def update_checkpoint(self, checkpoint_id: str, *, func=None, description=None, constraint_ids=None, args=None) -> dict[str, Any]: ...
def remove_checkpoint(self, checkpoint_id: str) -> dict[str, Any]: ...
def get_validator_script(self) -> dict[str, Any]: ...
def replace_validator_script(self, script: str | None) -> dict[str, Any]: ...
def artifact_state(self) -> dict[str, Any]: ...
```

Implementation notes:
- Keep graph state in `TGraphRuntime`; keep authored-check state in `BoundTGraphTools`.
- `validate()` must always use the live mutated authored-check/script state, not the original constructor kwargs.
- Do not add compatibility aliases like `set_checkpoint_script` or `patch_checkpoint`.

- [ ] **Step 4: Re-run the focused tool tests**

Run: `pytest tests/unit/tools/tgraph/test_graph_core.py -k "checkpoint or validator_script" -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/unit/tools/tgraph/test_graph_core.py src/trace/tools/tgraph/protocol.py
git commit -m "feat: add authored-check mutation tools"
```

### Task 6: Rewire logical repair to use provenance, grounded constraints, and full artifact writeback

**Files:**
- Modify: `src/trace/stages/logical/nodes/repair.py`
- Modify: `src/trace/stages/logical/prompts/repair.md`
- Modify: `tests/unit/stages/logical/test_repair_node.py`

- [ ] **Step 1: Write failing logical-repair tests**

```python
def test_logical_repair_node_injects_logical_constraints_into_prompt():
    ...
    assert "[logical_constraints]" in contents


def test_logical_repair_node_writes_back_mutated_checkpoints_and_script():
    ...
    assert result["draft_artifact"]["logical_checkpoints"][0]["description"] == "patched"
    assert result["draft_artifact"]["logical_validator_script"] == "def check_rule(tgraph, **kwargs):\\n    return []\\n"
```

- [ ] **Step 2: Run the logical-repair tests and verify they fail**

Run: `pytest tests/unit/stages/logical/test_repair_node.py -q`

Expected: FAIL because repair only exposes node/link tools, does not inject grounded constraints, and only writes back `tgraph_logical`.

- [ ] **Step 3: Implement full-artifact logical repair**

```python
state["draft_artifact"] = {
    **state["draft_artifact"],
    **bound_tools.artifact_state(),
}
```

Implementation notes:
- Add grounded logical constraints to repair context directly; do not add a legacy `get_constraint` tool in this pass.
- Update candidate-checkpoint selection to read `issue["provenance"]["constraint_ids"]` and `issue["provenance"]["check_id"]` before falling back to message text.
- Update the repair prompt to explicitly allow:
  - graph mutations
  - checkpoint mutations
  - validator-script replacement
- Update the tool allowlist language in the prompt so it lists `update_link` and the authored-check mutation tools.

- [ ] **Step 4: Re-run the logical-repair tests**

Run: `pytest tests/unit/stages/logical/test_repair_node.py tests/unit/stages/logical/test_logical_validator_node.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/trace/stages/logical/nodes/repair.py src/trace/stages/logical/prompts/repair.md tests/unit/stages/logical/test_repair_node.py tests/unit/stages/logical/test_logical_validator_node.py
git commit -m "feat: enable full logical artifact repair"
```

## Chunk 4: Cleanup, Contract Updates, and Final Verification

### Task 7: Remove leftover legacy references and align active docs/contracts

**Files:**
- Modify: `src/trace/tools/tgraph/contract.md`
- Modify: `src/trace/stages/logical/prompts/repair.md`
- Modify: any remaining `src/trace/**` or `tests/**` files found by search

- [ ] **Step 1: Run a search for forbidden leftovers**

Run: `rg -n "\"scope\"|scope:|checkpoint_\"|code.startswith\\(\"checkpoint_\"\\)" src tests`

Expected: only intentional matches in historical spec documents outside `src/` and active tests; zero matches in active runtime/test code after migration.

- [ ] **Step 2: Delete or rewrite leftover active-code references**

```text
- remove `scope` from active code paths
- remove `code.startswith("checkpoint_")` routing
- ensure tool docs mention `update_link`
- ensure custom-script examples call `issue()` without `scope`
```

- [ ] **Step 3: Run targeted regression suites**

Run: `pytest tests/unit/tools/tgraph/test_validation_issues.py tests/unit/tools/tgraph/test_graph_core.py tests/unit/stages/logical/test_logical_validator_node.py tests/unit/stages/logical/test_repair_node.py tests/unit/stages/physical/test_physical_validator_node.py -q`

Expected: PASS

- [ ] **Step 4: Run the full test suite**

Run: `pytest -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src tests docs/superpowers/plans/2026-04-12-logical-repair-authored-check-implementation.md
git commit -m "refactor: complete logical repair authored-check migration"
```

## Non-Goals During Implementation

- Reworking ground-stage schema again
- Introducing a statement compiler or semantic IR layer
- Making builder subordinate to authored checkpoints
- Designing physical-stage authored-check repair in this pass
- Preserving legacy `scope` or checkpoint-prefix compatibility paths

## Execution Notes

- Implement in chunk order. Chunk 1 must land before any stage-node work.
- Keep changes DRY: F4 provenance should be stamped in one place, inside `f4_intent.py`.
- Keep runtime ownership clean: graph mutations belong in `transaction.py` / `runtime.py`; authored-check mutations belong in `protocol.py`.
- If a chunk uncovers a larger hidden dependency, update this plan before continuing instead of adding ad hoc compatibility code.

