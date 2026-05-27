# TRACE Hard Migration To Standalone TGraph Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hard-migrate TRACE to the standalone `tgraph` engine so logical and physical stage artifacts use `graph/checkpoints/validator_script`, TRACE workflow stays `ground -> logical -> physical`, and no active code path depends on the old `trace.tools.tgraph` compatibility layer.

**Architecture:** Land the migration in lockstep. First extend standalone `tgraph` so F4 can execute checkpoints, builtin assert functions, and custom validator scripts through a stable read-only SDK. Then hard-cut TRACE stage artifacts, validators, repair tooling, prompts, and skill scripts to the new artifact shape, and finally delete the old TRACE-owned TGraph implementation and test references.

**Tech Stack:** Python 3.10+, Pydantic v2, Typer, pytest, LangGraph state flow, existing TRACE skill script test harness.

---

## Scope Notes

This spec touches multiple subsystems, but they are tightly coupled and should not be split into separate implementation plans. A partial rollout would leave the repo in a dual-schema state (`tgraph_logical` vs `graph`, old F4 vs new F4), which is exactly what this migration is trying to remove.

Use `@superpowers:test-driven-development` inside each chunk. Before claiming completion, run `@superpowers:verification-before-completion`.

If the execution harness cannot use subagents, execute this plan in the current session with `@superpowers:executing-plans`.

## File Structure Map

Create:

- `src/tgraph/operations/validate/checkpoints.py`: checkpoint models, registry, and builtin dispatch helpers.
- `src/tgraph/operations/validate/builtins.py`: implementations of `assert_node`, `assert_port`, `assert_link`, `assert_path`, `assert_group`, and `assert_graph`.
- `src/tgraph/operations/validate/view.py`: read-only `TGraphView`, CIDR helpers, path helpers, and issue helper for scripts.
- `src/tgraph/operations/validate/scripts.py`: custom validator script loading/execution sandbox for F4.
- `src/tgraph/operations/inspect/cidrs.py`: CIDR-centered inspect helpers that replace segment terminology in active TGraph inspect APIs.
- `src/tgraph/agent/playbooks/capabilities.md`: explicit TGraph capability contract for Codex/Claude Code/LangGraph agents.
- `src/trace/stages/artifacts.py`: shared `StageArtifact`, `LogicalArtifact`, and `PhysicalArtifact` models.
- `src/trace/stages/prompt_contracts.py`: TRACE-side loader that composes standalone TGraph capability/playbook docs into stage prompts.
- `src/trace/stages/logical/graph_seed.py`: logical graph seeding from grounded facts using standalone `tgraph`.
- `src/trace/stages/physical/graph_seed.py`: physical graph seeding from logical graph using standalone `tgraph`.
- `src/trace/stages/repair_tools.py`: thin repair-tool wrapper over standalone `tgraph` plus artifact checkpoint/script patch helpers.
- `tests/unit/tgraph/agent/test_capabilities.py`: targeted TGraph capability-contract tests.
- `tests/unit/tgraph/operations/test_validate_f4.py`: dedicated F4 checkpoint/script/registry tests.
- `tests/unit/stages/test_artifacts.py`: shared TRACE stage artifact model tests.
- `tests/unit/tgraph/operations/test_inspect_cidrs.py`: inspect-surface tests for CIDR-centered APIs.
- `tests/unit/stages/logical/test_prepare_node.py`: logical prepare-node tests.
- `tests/unit/stages/physical/test_prepare_node.py`: physical prepare-node tests.

Modify:

- `src/tgraph/operations/validate/policy.py`
- `src/tgraph/operations/validate/f4_intent.py`
- `src/tgraph/operations/validate/runner.py`
- `src/tgraph/operations/validate/__init__.py`
- `src/tgraph/operations/inspect/__init__.py`
- `src/tgraph/agent/protocol.py`
- `src/tgraph/agent/playbooks/authoring.md`
- `src/tgraph/agent/playbooks/repair.md`
- `src/tgraph/agent/playbooks/validation.md`
- `tests/unit/tgraph/agent/test_schemas.py`
- `src/trace/stages/common.py`
- `src/trace/stages/logical/schemas.py`
- `src/trace/stages/physical/schemas.py`
- `src/trace/stages/logical/state.py`
- `src/trace/stages/physical/state.py`
- `src/trace/stages/logical/nodes/prepare.py`
- `src/trace/stages/physical/nodes/prepare.py`
- `src/trace/stages/logical/nodes/author.py`
- `src/trace/stages/physical/nodes/author.py`
- `src/trace/stages/logical/nodes/builder.py`
- `src/trace/stages/physical/nodes/builder.py`
- `src/trace/stages/logical/nodes/validator.py`
- `src/trace/stages/physical/nodes/validator.py`
- `src/trace/stages/logical/nodes/repair.py`
- `src/trace/stages/physical/nodes/repair.py`
- `src/trace/stages/logical/prompts/author.md`
- `src/trace/stages/logical/prompts/builder.md`
- `src/trace/stages/logical/prompts/repair.md`
- `src/trace/stages/physical/prompts/author.md`
- `src/trace/stages/physical/prompts/builder.md`
- `src/trace/stages/physical/prompts/repair.md`
- `skills/tgraph-iac/scripts/trace_backend.py`
- `skills/tgraph-iac/scripts/tgraph_apply_patch.py`
- `skills/tgraph-iac/scripts/tgraph_inspect.py`
- `skills/tgraph-iac/scripts/tgraph_validate.py`
- `skills/tgraph-iac/scripts/tgraph_export.py`
- `tests/unit/tgraph/operations/test_validate.py`
- `tests/unit/config/test_prompts.py`
- `tests/unit/skills/test_tgraph_iac_scripts.py`
- `tests/unit/skills/test_tgraph_iac_trace_backend.py`
- `tests/unit/stages/logical/test_author_node.py`
- `tests/unit/stages/logical/test_builder_node.py`
- `tests/unit/stages/logical/test_logical_validator_node.py`
- `tests/unit/stages/logical/test_repair_node.py`
- `tests/unit/stages/physical/test_physical_author_node.py`
- `tests/unit/stages/physical/test_physical_builder_node.py`
- `tests/unit/stages/physical/test_physical_validator_node.py`
- `tests/unit/stages/physical/test_physical_repair_node.py`
- `tests/unit/stages/test_common_schemas.py`
- `tests/unit/stages/logical/test_prepare_node.py`
- `tests/unit/stages/physical/test_prepare_node.py`
- `tests/unit/stages/test_artifacts.py`
- `tests/unit/storage/test_run_storage.py`
- `tests/unit/runtime/test_reducers.py`
- `tests/integration/test_runtime_pipeline.py`
- `skills/tgraph-iac/SKILL.md`
- `skills/tgraph-iac/references/patch-protocol.md`
- `skills/tgraph-iac/references/tgraph-ir.md`
- `skills/tgraph-iac/references/validation.md`
- `skills/tgraph-iac/references/agent-workflows.md`

Delete:

- `src/tgraph/operations/inspect/segments.py`
- `src/trace/tools/tgraph/__init__.py`
- `src/trace/tools/tgraph/model.py`
- `src/trace/tools/tgraph/runtime.py`
- `src/trace/tools/tgraph/transaction.py`
- `src/trace/tools/tgraph/patch.py`
- `src/trace/tools/tgraph/export.py`
- `src/trace/tools/tgraph/derive.py`
- `src/trace/tools/tgraph/protocol.py`
- `src/trace/tools/tgraph/prompting.py`
- `src/trace/tools/tgraph/contract.md`
- `src/trace/tools/tgraph/contracts/core_schema.md`
- `src/trace/tools/tgraph/contracts/graph_validity.md`
- `src/trace/tools/tgraph/contracts/f4_checkpoint_sdk.md`
- `src/trace/tools/tgraph/contracts/custom_validator_sdk.md`
- `src/trace/tools/tgraph/contracts/mutation_tools.md`
- `src/trace/tools/tgraph/contracts/physical_metadata.md`
- `src/trace/tools/tgraph/validate/__init__.py`
- `src/trace/tools/tgraph/validate/types.py`
- `src/trace/tools/tgraph/validate/issues.py`
- `src/trace/tools/tgraph/validate/intent_sdk.py`
- `src/trace/tools/tgraph/validate/f1_format.py`
- `src/trace/tools/tgraph/validate/f2_schema.py`
- `src/trace/tools/tgraph/validate/f3_consistency.py`
- `src/trace/tools/tgraph/validate/f4_intent.py`
- `tests/unit/tools/tgraph/test_export.py`
- `tests/unit/tools/tgraph/test_graph_core.py`
- `tests/unit/tools/tgraph/test_model.py`
- `tests/unit/tools/tgraph/test_patch_protocol.py`
- `tests/unit/tools/tgraph/test_query.py`
- `tests/unit/tools/tgraph/test_validation_issues.py`

## Chunk 1: Extend Standalone TGraph F4 Into The Real Intent Engine

### Task 1: Make `tgraph.validate_graph()` execute checkpoints, registered functions, and validator scripts

**Files:**
- Create: `src/tgraph/operations/validate/checkpoints.py`
- Create: `src/tgraph/operations/validate/builtins.py`
- Create: `src/tgraph/operations/validate/view.py`
- Create: `src/tgraph/operations/validate/scripts.py`
- Modify: `src/tgraph/operations/validate/policy.py`
- Modify: `src/tgraph/operations/validate/f4_intent.py`
- Modify: `src/tgraph/operations/validate/runner.py`
- Modify: `src/tgraph/operations/validate/__init__.py`
- Create: `tests/unit/tgraph/operations/test_validate_f4.py`

- [ ] **Step 1: Write the failing F4 tests**

Add targeted tests to `tests/unit/tgraph/operations/test_validate_f4.py` for:

```python
def test_validate_graph_dispatches_registered_checkpoint_batch() -> None:
    graph = TGraph.model_validate({
        "stage": "logical",
        "nodes": [{"id": "PLC1", "type": "computer", "label": "PLC1", "ports": []}],
        "links": [],
    })

    def assert_node_exists(tgraph, *, node, **kwargs):
        return [] if tgraph.node(node) is not None else [issue("missing_node", f"{node} must exist", targets=[node])]

    registry = CheckpointRegistry()
    registry.register("assert_node_exists", assert_node_exists)

    report = validate_graph(
        graph,
        context=ValidationContext(
            checkpoints=[CheckpointSpec(id="cp1", func="assert_node_exists", args={"node": "PLC1"})],
            registry=registry,
        ),
    )

    assert report.ok is True


def test_validate_graph_runs_unreferenced_script_checks_once() -> None:
    graph = TGraph.model_validate({"stage": "logical", "nodes": [], "links": []})
    script = '''
def check_empty_graph(tgraph, **kwargs):
    if tgraph.nodes():
        return []
    return [issue("empty_graph", "graph must not be empty", targets=[])]
'''

    report = validate_graph(graph, context=ValidationContext(validator_script=script))

    assert [item.code for item in report.issues] == ["empty_graph"]


def test_validate_graph_dispatches_registered_checkpoint_functions() -> None:
    graph = TGraph.model_validate({"stage": "logical", "nodes": [{"id": "R1", "type": "router", "label": "R1", "ports": []}], "links": []})

    def assert_label_is(tgraph, *, node, label, **kwargs):
        actual = tgraph.node(node)
        if actual and actual["label"] == label:
            return []
        return [issue("wrong_label", f"{node} must use label {label}", targets=[node])]

    registry = CheckpointRegistry()
    registry.register("assert_label_is", assert_label_is)

    report = validate_graph(
        graph,
        context=ValidationContext(
            checkpoints=[CheckpointSpec(id="cp_label", func="assert_label_is", args={"node": "R1", "label": "R1"})],
            registry=registry,
        ),
    )

    assert report.ok is True


def test_validate_graph_runs_script_function_referenced_by_checkpoint() -> None:
    graph = TGraph.model_validate({
        "stage": "physical",
        "nodes": [{
            "id": "PLC1",
            "type": "computer",
            "label": "PLC1",
            "ports": [{"id": "PLC1_p1", "ip": "192.168.10.10", "cidr": "192.168.10.0/24"}],
        }],
        "links": [],
    })
    script = '''
def check_expected_cidr(tgraph, node, cidr, **kwargs):
    if tgraph.node_has_port_in_cidr(node, cidr):
        return []
    return [issue("missing_cidr", f"{node} must have a port in {cidr}", targets=[node])]
'''

    report = validate_graph(
        graph,
        context=ValidationContext(
            checkpoints=[CheckpointSpec(id="cp_cidr", func="check_expected_cidr", args={"node": "PLC1", "cidr": "192.168.10.0/24"})],
            validator_script=script,
        ),
    )

    assert report.ok is True


def test_validate_graph_reports_unknown_checkpoint_function() -> None:
    graph = TGraph.model_validate({"stage": "logical", "nodes": [], "links": []})
    report = validate_graph(
        graph,
        context=ValidationContext(checkpoints=[CheckpointSpec(id="cp_missing", func="does_not_exist", args={})]),
    )
    assert any(item.code == "unknown_checkpoint_function" for item in report.issues)


def test_validate_graph_reports_validator_script_exception() -> None:
    graph = TGraph.model_validate({"stage": "logical", "nodes": [], "links": []})
    script = '''
def check_boom(tgraph, **kwargs):
    raise RuntimeError("boom")
'''
    report = validate_graph(graph, context=ValidationContext(validator_script=script))
    assert any(item.code == "validator_script_exception" for item in report.issues)


def test_validate_graph_reports_validator_script_timeout() -> None:
    graph = TGraph.model_validate({"stage": "logical", "nodes": [], "links": []})
    script = '''
def check_slow(tgraph, **kwargs):
    while True:
        pass
'''
    report = validate_graph(graph, context=ValidationContext(validator_script=script, script_timeout_seconds=0.01))
    assert any(item.code == "validator_script_timeout" for item in report.issues)


def test_validate_graph_normalizes_script_return_shapes() -> None:
    graph = TGraph.model_validate({"stage": "logical", "nodes": [], "links": []})
    script = '''
def check_dict_issue(tgraph, **kwargs):
    return {"code": "dict_issue", "message": "returned as dict"}
'''
    report = validate_graph(graph, context=ValidationContext(validator_script=script))
    assert any(item.code == "dict_issue" for item in report.issues)
```

- [ ] **Step 2: Run the targeted test file to verify the failures**

Run: `python -m pytest tests/unit/tgraph/operations/test_validate_f4.py -q`

Expected: FAIL because `ValidationContext` does not yet accept the new F4 fields and the dispatch/sandbox behaviors do not exist yet.

- [ ] **Step 3: Implement typed checkpoint models and registry plumbing**

Implement:

- `ValidationContext` fields in `src/tgraph/operations/validate/policy.py`:
  - `checkpoints: list[CheckpointSpec] = Field(default_factory=list)`
  - `validator_script: str | None = None`
  - `references: dict[str, TGraph] = Field(default_factory=dict)`
  - `registry: CheckpointRegistry | None = None`
  - `script_timeout_seconds: float = 2.0`
- `CheckpointSpec`, `CheckpointResult`, and `CheckpointRegistry` in `src/tgraph/operations/validate/checkpoints.py`.
  - Canonical checkpoint schema for the whole migration is:
    - required: `id`, `func`, `args`
    - optional: `description: str | None = None`, `constraint_ids: list[str] = []`
  - All TRACE and TGraph layers use this one schema; do not leave checkpoint shape as an open choice.
- a minimal builtin dispatch module in `src/tgraph/operations/validate/builtins.py` with only the checkpoint functions needed for Task 1 pass conditions:
  - `assert_node` for node-existence checks
  - `assert_graph` for `preserve_topology_from`

- [ ] **Step 4: Re-run the F4 test file**

Run: `python -m pytest tests/unit/tgraph/operations/test_validate_f4.py -q`

Expected: FAIL on missing `TGraphView`, script sandboxing, and F4 orchestration.

- [ ] **Step 5: Implement `TGraphView` and validator-script sandboxing**

Implement:

- `TGraphView` in `src/tgraph/operations/validate/view.py` with read-only helpers:
  - `node()`, `nodes()`, `port()`, `ports()`, `link()`, `links()`
  - `neighbors()`, `degree()`, `connected()`, `path_exists()`, `paths()`
  - `all_paths_include()`, `any_path_include()`, `all_paths_exclude()`, `group_paths_include()`, `group_isolated()`
  - `cidrs()`, `ports_in_cidr()`, `nodes_in_cidr()`, `node_has_port_in_cidr()`, `switch_cidr()`, `ports_share_cidr()`, `ip_in_cidr()`
  - `issue(code, message, severity="error", targets=None, location=None, details=None)` helper
- script loading/execution in `src/tgraph/operations/validate/scripts.py` with a safe globals dict that exposes only `issue`, `ipaddress`, `re`, and plain builtins required for function definitions.
- validator scripts must execute in a separate process with a hard timeout derived from `script_timeout_seconds`; do not use in-process signal/thread hacks for busy-loop interruption. Convert timeout or child-process exceptions into validation issues rather than hanging the caller.

- [ ] **Step 6: Re-run the F4 test file**

Run: `python -m pytest tests/unit/tgraph/operations/test_validate_f4.py -q`

Expected: FAIL on missing orchestration/dispatch in `f4_intent.py`.

- [ ] **Step 7: Implement F4 orchestration in `f4_intent.py` and `runner.py`**

Implement `f4_intent.py` entrypoints that:

- keep existing topology/required-field checks
- resolve checkpoint functions in strict order: builtin -> `context.registry` -> `validator_script`
- auto-run exported script functions whose names start with `check_` exactly once when they are not referenced by any checkpoint
- run checkpoint batch
- merge all returned issues into one validation report
- return `unknown_checkpoint_function`, `validator_script_exception`, or `validator_script_timeout` issues instead of throwing uncaught exceptions

- [ ] **Step 8: Re-run the F4 test file**

Run: `python -m pytest tests/unit/tgraph/operations/test_validate_f4.py -q`

Expected: PASS.

- [ ] **Step 9: Commit the F4 runtime surface**

```bash
git add src/tgraph/operations/validate tests/unit/tgraph/operations/test_validate_f4.py
git commit -m "feat: add standalone tgraph f4 intent engine"
```

### Task 2: Add the six builtin assert functions and CIDR-centered script helpers

**Files:**
- Modify: `src/tgraph/operations/validate/builtins.py`
- Modify: `src/tgraph/operations/validate/checkpoints.py`
- Modify: `src/tgraph/operations/validate/view.py`
- Modify: `tests/unit/tgraph/operations/test_validate_f4.py`

- [ ] **Step 1: Write the failing builtin assertion tests**

Extend `tests/unit/tgraph/operations/test_validate_f4.py` with focused builtin coverage:

```python
def test_assert_port_supports_cidr_without_segment_terms() -> None:
    graph = TGraph.model_validate({
        "stage": "physical",
        "nodes": [{
            "id": "PLC1",
            "type": "computer",
            "label": "PLC1",
            "ports": [{"id": "PLC1_p1", "ip": "192.168.10.10", "cidr": "192.168.10.0/24"}],
        }],
        "links": [],
    })

    report = validate_graph(
        graph,
        context=ValidationContext(
            checkpoints=[CheckpointSpec(id="cidr", func="assert_port", args={"node": "PLC1", "cidr": "192.168.10.0/24"})],
        ),
    )

    assert report.ok is True


def test_assert_path_supports_required_hops() -> None:
    graph = TGraph.model_validate({
        "stage": "logical",
        "nodes": [
            {"id": "WEB1", "type": "computer", "label": "WEB1", "ports": [{"id": "WEB1_p1", "ip": "", "cidr": ""}]},
            {"id": "FW1", "type": "router", "label": "FW1", "ports": [{"id": "FW1_p1", "ip": "", "cidr": ""}, {"id": "FW1_p2", "ip": "", "cidr": ""}]},
            {"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [{"id": "PLC1_p1", "ip": "", "cidr": ""}]},
        ],
        "links": [
            {"id": "WEB1__FW1", "from_port": "WEB1_p1", "to_port": "FW1_p1", "from_node": "WEB1", "to_node": "FW1"},
            {"id": "FW1__PLC1", "from_port": "FW1_p2", "to_port": "PLC1_p1", "from_node": "FW1", "to_node": "PLC1"},
        ],
    })

    report = validate_graph(
        graph,
        context=ValidationContext(
            checkpoints=[CheckpointSpec(
                id="path",
                func="assert_path",
                args={"from": "WEB1", "to": "PLC1", "exists": True, "must_include": ["FW1"], "max_hops": 2},
            )],
        ),
    )

    assert report.ok is True


def test_script_sdk_exposes_cidr_helpers() -> None:
    graph = TGraph.model_validate({
        "stage": "physical",
        "nodes": [{
            "id": "PLC1",
            "type": "computer",
            "label": "PLC1",
            "ports": [{"id": "PLC1_p1", "ip": "192.168.10.10", "cidr": "192.168.10.0/24"}],
        }],
        "links": [],
    })
    script = '''
def check_lan(tgraph, **kwargs):
    if tgraph.node_has_port_in_cidr("PLC1", "192.168.10.0/24") and tgraph.cidrs() == ["192.168.10.0/24"]:
        return []
    return [issue("missing_cidr", "PLC1 must be in LAN", targets=["PLC1"])]
'''

    report = validate_graph(graph, context=ValidationContext(validator_script=script))

    assert report.ok is True


def test_assert_link_reports_stable_issue_code_when_link_is_missing() -> None:
    graph = TGraph.model_validate({"stage": "logical", "nodes": [], "links": []})
    report = validate_graph(
        graph,
        context=ValidationContext(
            checkpoints=[CheckpointSpec(id="link", func="assert_link", args={"between": ["A", "B"], "exists": True})],
        ),
    )
    assert any(item.code == "missing_link" for item in report.issues)


def test_assert_group_requires_paths_through_named_nodes() -> None:
    graph = TGraph.model_validate({
        "stage": "logical",
        "nodes": [
            {"id": "WEB1", "type": "computer", "label": "WEB1", "ports": [{"id": "WEB1_p1", "ip": "", "cidr": ""}]},
            {"id": "FW1", "type": "router", "label": "FW1", "ports": [{"id": "FW1_p1", "ip": "", "cidr": ""}, {"id": "FW1_p2", "ip": "", "cidr": ""}]},
            {"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [{"id": "PLC1_p1", "ip": "", "cidr": ""}]},
        ],
        "links": [
            {"id": "WEB1__FW1", "from_port": "WEB1_p1", "to_port": "FW1_p1", "from_node": "WEB1", "to_node": "FW1"},
            {"id": "FW1__PLC1", "from_port": "FW1_p2", "to_port": "PLC1_p1", "from_node": "FW1", "to_node": "PLC1"},
        ],
    })
    report = validate_graph(
        graph,
        context=ValidationContext(
            checkpoints=[CheckpointSpec(
                id="group_path",
                func="assert_group",
                args={"sources": ["WEB1"], "targets": ["PLC1"], "paths": {"exists": True, "must_include": ["FW1"]}},
            )],
        ),
    )
    assert report.ok is True


def test_assert_graph_uses_reference_graph_for_topology_preservation() -> None:
    logical = TGraph.model_validate({"stage": "logical", "nodes": [{"id": "R1", "type": "router", "label": "R1", "ports": []}], "links": []})
    physical = TGraph.model_validate({"stage": "physical", "nodes": [], "links": []})
    report = validate_graph(
        physical,
        context=ValidationContext(
            checkpoints=[CheckpointSpec(id="cp_topology", func="assert_graph", args={"preserve_topology_from": "logical"})],
            references={"logical": logical},
        ),
    )
    assert any(item.code == "topology_not_preserved" for item in report.issues)
```

- [ ] **Step 2: Run the validate test file again**

Run: `python -m pytest tests/unit/tgraph/operations/test_validate_f4.py -q`

Expected: FAIL on missing builtin handlers and/or missing CIDR helper methods.

- [ ] **Step 3: Implement only the six builtin asserts**

Implement `src/tgraph/operations/validate/builtins.py` so the public builtin set is exactly:

```python
BUILTIN_CHECKPOINTS = {
    "assert_node": assert_node,
    "assert_port": assert_port,
    "assert_link": assert_link,
    "assert_path": assert_path,
    "assert_group": assert_group,
    "assert_graph": assert_graph,
}
```

Rules:

- Do not add `segment` terminology anywhere in function names, args, docs, or helper APIs.
- `assert_graph` may resolve `preserve_topology_from` only through `context.references`.
- `assert_group` may loop over multiple nodes/paths but must not create new domain concepts like zone or DMZ.
- Supported arg surface must be documented inline in code comments or tests for each builtin:
  - `assert_node`: `node`, `exists`, `type`, `fields`, `degree`, `connected_to`
  - `assert_port`: `node`, `port`, `exists`, `ip`, `cidr`, `connected_to`
  - `assert_link`: `between`, `exists`
  - `assert_path`: `from`, `to`, `exists`, `must_include`, `must_exclude`, `max_hops`
  - `assert_group`: `nodes` and/or `sources`/`targets`, plus `cidr` or nested `paths`
  - `assert_graph`: `stage`, `preserve_topology_from`, `node_count`, `link_count`
- Errors should use stable issue codes including `checkpoint_failed`, `missing_node`, `missing_path`, `missing_cidr`, `wrong_stage`, and `topology_not_preserved`.

- [ ] **Step 4: Re-run the validate test file**

Run: `python -m pytest tests/unit/tgraph/operations/test_validate_f4.py -q`

Expected: PASS.

- [ ] **Step 5: Commit builtin assert coverage**

```bash
git add src/tgraph/operations/validate tests/unit/tgraph/operations/test_validate_f4.py
git commit -m "feat: add builtin standalone tgraph intent assertions"
```

### Task 2B: Remove `segment` terminology from active TGraph inspect APIs

**Files:**
- Create: `src/tgraph/operations/inspect/cidrs.py`
- Modify: `src/tgraph/operations/inspect/__init__.py`
- Create: `tests/unit/tgraph/operations/test_inspect_cidrs.py`
- Delete: `src/tgraph/operations/inspect/segments.py`
- Modify: `tests/unit/tgraph/operations/test_inspect.py`

- [ ] **Step 1: Write the failing inspect-surface tests**

Add tests that assert:

```python
def test_inspect_exports_cidr_centered_helpers() -> None:
    from tgraph.operations.inspect import list_cidrs, nodes_in_cidr, ports_in_cidr

    assert callable(list_cidrs)
    assert callable(nodes_in_cidr)
    assert callable(ports_in_cidr)


def test_inspect_module_does_not_export_segment_helpers() -> None:
    import tgraph.operations.inspect as inspect_mod

    assert not hasattr(inspect_mod, "segments_for_switch")
    assert not hasattr(inspect_mod, "nodes_on_segment")
```

- [ ] **Step 2: Run the inspect tests**

Run: `python -m pytest tests/unit/tgraph/operations/test_inspect.py tests/unit/tgraph/operations/test_inspect_cidrs.py -q`

Expected: FAIL because active inspect APIs still expose the `segments.py` surface.

- [ ] **Step 3: Implement CIDR-centered inspect exports**

Implementation rules:

- replace `segments.py` with `cidrs.py`
- public inspect exports must use CIDR-centered names only
- any behavior still needed from the old inspect surface must be preserved through CIDR-oriented helpers, not through `segment` aliases
- update tests so active code no longer mentions `segment` inspect names

- [ ] **Step 4: Re-run the inspect tests**

Run: `python -m pytest tests/unit/tgraph/operations/test_inspect.py tests/unit/tgraph/operations/test_inspect_cidrs.py -q`

Expected: PASS.

- [ ] **Step 5: Commit inspect-surface cleanup**

```bash
git add src/tgraph/operations/inspect tests/unit/tgraph/operations/test_inspect.py tests/unit/tgraph/operations/test_inspect_cidrs.py
git commit -m "refactor: replace segment inspect surface with cidr helpers"
```

### Task 3: Publish the agent-facing capability boundary

**Files:**
- Create: `src/tgraph/agent/playbooks/capabilities.md`
- Create: `tests/unit/tgraph/agent/test_capabilities.py`
- Modify: `src/tgraph/agent/playbooks/authoring.md`
- Modify: `src/tgraph/agent/playbooks/repair.md`
- Modify: `src/tgraph/agent/playbooks/validation.md`
- Modify: `src/tgraph/agent/protocol.py`
- Modify: `tests/unit/tgraph/agent/test_schemas.py`

- [ ] **Step 1: Write failing contract tests**

Add tests that assert the agent docs and protocol surface:

```python
def test_tgraph_capability_contract_forbids_unsupported_ir_fields() -> None:
    text = Path("src/tgraph/agent/playbooks/capabilities.md").read_text(encoding="utf-8")
    assert "software" in text
    assert "packages" in text
    assert "segment" in text
    assert "cannot" in text.lower()


def test_tgraph_capability_contract_explains_image_translation() -> None:
    text = Path("src/tgraph/agent/playbooks/capabilities.md").read_text(encoding="utf-8")
    assert "install software" in text.lower()
    assert "image" in text.lower()


def test_agent_playbooks_use_graph_checkpoint_validator_shape() -> None:
    for path in (
        "src/tgraph/agent/playbooks/authoring.md",
        "src/tgraph/agent/playbooks/repair.md",
        "src/tgraph/agent/playbooks/validation.md",
    ):
        text = Path(path).read_text(encoding="utf-8")
        assert "graph" in text
        assert "checkpoints" in text
        assert "validator_script" in text
        assert "tgraph_logical" not in text
        assert "profile" not in text


def test_agent_protocol_examples_use_batch_patch_only() -> None:
    text = Path("src/tgraph/agent/protocol.py").read_text(encoding="utf-8")
    assert "batch patch" in text.lower() or "apply_patch" in text
    assert "transaction" not in text.lower()
```

- [ ] **Step 2: Run the prompt/config tests**

Run: `python -m pytest tests/unit/tgraph/agent/test_capabilities.py tests/unit/tgraph/agent/test_schemas.py -q`

Expected: FAIL because `capabilities.md` does not exist and the current TGraph playbooks/protocol still mention older contract shapes.

- [ ] **Step 3: Write the capability contract and wire it into TGraph agent docs**

Document:

- what TGraph can express directly (`nodes/ports/links/ip/cidr/image/flavor`, `stage`, batch patch, validation, canonical JSON)
- what TGraph cannot do directly (software install, package manager steps, provider catalog lookup, zone/segment/firewall-rule IR fields)
- indirect translation rules:
  - software install request -> resolve an image outside TGraph, then set `node.image`
  - isolation requirement -> encode as checkpoints/path constraints
  - provider/image availability -> caller-owned catalog lookup, not TGraph core
- a short decision ladder agents should follow before writing patches

Also update `protocol.py` and the existing playbooks so they point to `graph/checkpoints/validator_script` and the new F4 surface.

- [ ] **Step 4: Re-run prompt/config tests**

Run: `python -m pytest tests/unit/tgraph/agent/test_capabilities.py tests/unit/tgraph/agent/test_schemas.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the capability contract**

```bash
git add src/tgraph/agent src/tgraph/agent/playbooks/capabilities.md tests/unit/tgraph/agent/test_capabilities.py tests/unit/tgraph/agent/test_schemas.py
git commit -m "docs: add standalone tgraph capability contract"
```

## Chunk 2: Hard-Cut TRACE Stage Artifacts To `graph/checkpoints/validator_script`

### Task 4: Introduce shared stage artifact models and update state/storage surfaces

**Files:**
- Create: `src/trace/stages/artifacts.py`
- Create: `tests/unit/stages/test_artifacts.py`
- Modify: `src/trace/stages/common.py`
- Modify: `src/trace/stages/logical/schemas.py`
- Modify: `src/trace/stages/physical/schemas.py`
- Modify: `src/trace/stages/logical/state.py`
- Modify: `src/trace/stages/physical/state.py`
- Modify: `tests/unit/storage/test_run_storage.py`
- Modify: `tests/unit/runtime/test_reducers.py`

- [ ] **Step 1: Write the failing artifact-shape tests**

Add targeted tests to `tests/unit/stages/test_artifacts.py`, `tests/unit/storage/test_run_storage.py`, and `tests/unit/runtime/test_reducers.py` so they expect:

```python
def test_logical_author_artifact_uses_shared_checkpoint_fields() -> None:
    assert "checkpoints" in LogicalAuthorArtifact.model_fields
    assert "validator_script" in LogicalAuthorArtifact.model_fields
    assert "logical_checkpoints" not in LogicalAuthorArtifact.model_fields


def test_logical_artifact_uses_shared_graph_shape() -> None:
    assert "graph" in LogicalArtifact.model_fields
    assert "checkpoints" in LogicalArtifact.model_fields
    assert "validator_script" in LogicalArtifact.model_fields
    assert "tgraph_logical" not in LogicalArtifact.model_fields


def test_physical_artifact_rejects_wrong_stage() -> None:
    with pytest.raises(ValidationError):
        PhysicalArtifact.model_validate({
            "graph": {"stage": "logical", "nodes": [], "links": []},
            "checkpoints": [],
            "validator_script": None,
        })


def test_run_storage_persists_graph_stage_field() -> None:
    storage = RunStorage(tmp_path / "runs")
    storage.initialize_run(run_id="run-001", run_payload={"run_id": "run-001", "status": "running"})
    artifact = {"graph": {"stage": "logical", "nodes": [], "links": []}, "checkpoints": [], "validator_script": None}
    storage.write_stage_snapshot(
        run_id="run-001",
        stage_id="logical",
        artifact=artifact,
        evaluation={"ok": True, "issues": []},
        summary={"attempts_used": 1},
        messages=[],
        tool_journal=[],
        history_name="repair_history",
        history_entries=[],
        events=[],
    )
    payload = json.loads((tmp_path / "runs" / "run-001" / "logical" / "artifact.json").read_text(encoding="utf-8"))
    assert payload["graph"]["stage"] == "logical"
    assert payload["checkpoints"] == []
    assert payload["validator_script"] is None


def test_reducers_preserve_graph_artifact_without_stage_specific_field_names() -> None:
    state = {"artifacts": {"logical": {"graph": {"stage": "logical", "nodes": [], "links": []}, "checkpoints": [], "validator_script": None}}}
    assert "tgraph_logical" not in state["artifacts"]["logical"]
```

Update `tests/unit/stages/test_common_schemas.py` so it matches the canonical checkpoint shape used everywhere in this migration:

- preserve optional `description` and `constraint_ids` on `CheckpointSpec`

Do not leave `test_common_schemas.py` asserting a different schema than the runtime model.

- [ ] **Step 2: Run the schema/storage tests**

Run: `python -m pytest tests/unit/stages/test_artifacts.py tests/unit/storage/test_run_storage.py tests/unit/runtime/test_reducers.py -q`

Expected: FAIL because the shared artifact models do not exist yet and the storage test file still asserts the old `tgraph_logical` payload shape.

- [ ] **Step 3: Implement the shared artifact models**

Implement `src/trace/stages/artifacts.py`:

```python
class StageArtifact(BaseModel):
    graph: TGraph
    checkpoints: list[CheckpointSpec] = Field(default_factory=list)
    validator_script: str | None = None


class LogicalArtifact(StageArtifact):
    @model_validator(mode="after")
    def _ensure_logical_stage(self) -> "LogicalArtifact":
        if self.graph.stage != "logical":
            raise ValueError("logical artifact graph must use stage='logical'")
        return self


class PhysicalArtifact(StageArtifact):
    @model_validator(mode="after")
    def _ensure_physical_stage(self) -> "PhysicalArtifact":
        if self.graph.stage != "physical":
            raise ValueError("physical artifact graph must use stage='physical'")
        return self
```

Then:

- make `trace.stages.common.CheckpointSpec` a re-export of `tgraph.operations.validate.checkpoints.CheckpointSpec`
- migrate `LogicalAuthorArtifact` and `PhysicalAuthorArtifact` to the same `checkpoints` / `validator_script` field names used by the final stage artifacts
- re-export shared artifact models from `logical/schemas.py` and `physical/schemas.py`
- update storage/reducer assumptions to preserve `graph/checkpoints/validator_script`
- update `src/trace/stages/logical/state.py` and `src/trace/stages/physical/state.py` so the typed state surfaces clearly use:
  - `working_graph: dict[str, Any]`
  - `draft_artifact: dict[str, Any]`
  - `logical_artifact` / `physical_artifact` in the shared artifact shape

- [ ] **Step 4: Re-run the schema/storage tests**

Run: `python -m pytest tests/unit/stages/test_artifacts.py tests/unit/storage/test_run_storage.py tests/unit/runtime/test_reducers.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the artifact hard cut**

```bash
git add src/trace/stages/artifacts.py src/trace/stages/common.py src/trace/stages/logical/schemas.py src/trace/stages/physical/schemas.py src/trace/stages/logical/state.py src/trace/stages/physical/state.py tests/unit/stages/test_artifacts.py tests/unit/stages/test_common_schemas.py tests/unit/storage/test_run_storage.py tests/unit/runtime/test_reducers.py
git commit -m "refactor: hard cut trace stage artifacts to standalone graph shape"
```

### Task 5: Move graph seeding out of `trace.tools.tgraph.derive` and onto standalone `tgraph`

**Files:**
- Create: `src/trace/stages/logical/graph_seed.py`
- Create: `src/trace/stages/physical/graph_seed.py`
- Create: `tests/unit/stages/logical/test_prepare_node.py`
- Create: `tests/unit/stages/physical/test_prepare_node.py`
- Modify: `src/trace/stages/logical/nodes/prepare.py`
- Modify: `src/trace/stages/physical/nodes/prepare.py`

- [ ] **Step 1: Write the failing seed/prepare tests**

Add these concrete tests:

```python
def test_logical_prepare_seeds_standalone_logical_graph() -> None:
    result = prepare_node(state)
    assert result["working_graph"]["stage"] == "logical"
    assert "profile" not in result["working_graph"]
    assert result["draft_artifact"] == {
        "graph": result["working_graph"],
        "checkpoints": [],
        "validator_script": None,
    }


def test_physical_prepare_copies_logical_graph_and_carries_checkpoint_context() -> None:
    state = {
        "logical_artifact": {
            "graph": {"stage": "logical", "nodes": [{"id": "R1", "type": "router", "label": "R1", "ports": []}], "links": []},
            "checkpoints": [{"id": "cp1", "func": "assert_graph", "args": {"stage": "logical"}}],
            "validator_script": "def check_logical(tgraph, **kwargs): return []",
        }
    }
    result = prepare_node(state)
    assert result["working_graph"]["stage"] == "physical"
    assert result["working_graph"]["nodes"] == state["logical_artifact"]["graph"]["nodes"]
    assert result["draft_artifact"]["checkpoints"][0]["id"] == "cp1"
    assert result["draft_artifact"]["validator_script"] == "def check_logical(tgraph, **kwargs): return []"
    assert state["logical_artifact"]["graph"]["stage"] == "logical"


def test_logical_prepare_expands_node_groups_with_existing_behavior() -> None:
    grounded = {"node_groups": [{"type": "computer", "members": ["PLC[1..2]"]}], "logical_constraints": [], "physical_constraints": []}
    result = prepare_node({"ground_artifact": grounded})
    assert [node["id"] for node in result["working_graph"]["nodes"]] == ["PLC1", "PLC2"]
```

- [ ] **Step 2: Run only the prepare/builder tests**

Run: `python -m pytest tests/unit/stages/logical/test_prepare_node.py tests/unit/stages/physical/test_prepare_node.py -q`

Expected: FAIL because prepare nodes still call `trace.tools.tgraph.derive` and return old-profile graphs.

- [ ] **Step 3: Implement standalone seed helpers**

Implement:

- `build_logical_seed_graph(ground_artifact: dict[str, Any]) -> TGraph` in `src/trace/stages/logical/graph_seed.py`
- `build_physical_seed_graph(logical_graph: TGraph) -> TGraph` in `src/trace/stages/physical/graph_seed.py`

Rules:

- logical seed returns canonical `{"stage": "logical", "nodes": [], "links": []}` with grounded nodes expanded before final normalization
- physical seed copies normalized logical topology and changes only `stage` to `"physical"`
- move the existing `expand_node_groups` behavior into `src/trace/stages/logical/graph_seed.py` unchanged and cover it with the test above
- `logical.prepare` seeds `draft_artifact={"graph": working_graph, "checkpoints": [], "validator_script": None}`
- `physical.prepare` seeds `draft_artifact` from the physical graph and carries `logical_artifact["checkpoints"]` / `logical_artifact["validator_script"]` forward until the physical author step overwrites them

- [ ] **Step 4: Re-run the prepare/builder tests**

Run: `python -m pytest tests/unit/stages/logical/test_prepare_node.py tests/unit/stages/physical/test_prepare_node.py -q`

Expected: PASS.

- [ ] **Step 5: Commit seeding migration**

```bash
git add src/trace/stages/logical/graph_seed.py src/trace/stages/physical/graph_seed.py src/trace/stages/logical/nodes/prepare.py src/trace/stages/physical/nodes/prepare.py tests/unit/stages/logical/test_prepare_node.py tests/unit/stages/physical/test_prepare_node.py
git commit -m "refactor: seed trace stages from standalone tgraph"
```

## Chunk 3: Migrate TRACE Stage Nodes, Prompts, And Repair Tooling

### Task 6: Rewire author, builder, and validator nodes to the new artifact schema

**Files:**
- Modify: `src/trace/stages/logical/nodes/author.py`
- Modify: `src/trace/stages/physical/nodes/author.py`
- Modify: `src/trace/stages/logical/nodes/builder.py`
- Modify: `src/trace/stages/physical/nodes/builder.py`
- Modify: `src/trace/stages/logical/nodes/validator.py`
- Modify: `src/trace/stages/physical/nodes/validator.py`
- Modify: `src/trace/stages/logical/schemas.py`
- Modify: `src/trace/stages/physical/schemas.py`
- Modify: `tests/unit/stages/logical/test_author_node.py`
- Modify: `tests/unit/stages/logical/test_builder_node.py`
- Modify: `tests/unit/stages/logical/test_logical_validator_node.py`
- Modify: `tests/unit/stages/physical/test_physical_author_node.py`
- Modify: `tests/unit/stages/physical/test_physical_builder_node.py`
- Modify: `tests/unit/stages/physical/test_physical_validator_node.py`

- [ ] **Step 1: Write the failing node tests**

Update tests to expect:

```python
assert result["author_output"] == {"checkpoints": [], "validator_script": None}
assert result["draft_artifact"]["graph"]["stage"] == "logical"
assert result["draft_artifact"]["checkpoints"] == [
    {"id": "cp_router", "func": "assert_node", "args": {"node": "R1", "exists": True}},
]
assert "tgraph_logical" not in result["draft_artifact"]
```

Also add a physical validator test that proves topology preservation now flows through standalone `ValidationContext.references`:

```python
def test_physical_validator_passes_logical_reference_graph_to_tgraph_validate() -> None:
    state = {
        "logical_artifact": {
            "graph": {"stage": "logical", "nodes": [{"id": "R1", "type": "router", "label": "R1", "ports": []}], "links": []},
            "checkpoints": [],
            "validator_script": None,
        },
        "draft_artifact": {
            "graph": {"stage": "physical", "nodes": [], "links": []},
            "checkpoints": [{"id": "cp_topology", "func": "assert_graph", "args": {"preserve_topology_from": "logical"}}],
            "validator_script": None,
        },
        "author_output": {"checkpoints": [{"id": "cp_topology", "func": "assert_graph", "args": {"preserve_topology_from": "logical"}}], "validator_script": None},
    }
    result = validator_node(state)
    assert result["validation"]["ok"] is False
    assert any(issue.code == "topology_not_preserved" for issue in result["validation"]["issues"])
```

- [ ] **Step 2: Run the stage-node tests**

Run: `python -m pytest tests/unit/stages/logical/test_author_node.py tests/unit/stages/logical/test_builder_node.py tests/unit/stages/logical/test_logical_validator_node.py tests/unit/stages/physical/test_physical_author_node.py tests/unit/stages/physical/test_physical_builder_node.py tests/unit/stages/physical/test_physical_validator_node.py -q`

Expected: FAIL because the nodes still use old field names and `TGraphRuntime`.

- [ ] **Step 3: Implement the builder/validator hard cut**

Implementation rules:

- author nodes return `{"checkpoints": [CheckpointSpec(id="cp1", func="assert_node", args={"node": "R1", "exists": True})], "validator_script": None | "def check_x(tgraph, **kwargs): return []"}` 
- define builder-specific response schemas in `logical/schemas.py` and `physical/schemas.py` so builder output may omit `checkpoints` and `validator_script` while still requiring `graph`
- builder nodes normalize only the graph body and must not silently rewrite authored checkpoint context
- if builder output omits `checkpoints` or `validator_script`, copy them from `state["author_output"]`
- if builder output includes `checkpoints` and/or `validator_script`, they must match `state["author_output"]` byte-for-byte; otherwise raise `ValueError("builder must not rewrite authored checkpoint context")`
- builder nodes persist `{"graph": normalize_graph(graph), "checkpoints": authored_checkpoints, "validator_script": authored_validator_script}`
- validator nodes call standalone `validate_graph(graph, context=ValidationContext(checkpoints=artifact["checkpoints"], validator_script=artifact["validator_script"], references={"logical": logical_artifact["graph"]} if artifact["graph"]["stage"] == "physical" else {}))` directly
- physical validator passes:
  - `preserve_topology_from=logical_artifact["graph"]`
  - `required_node_fields=["image", "flavor"]`
  - `checkpoints=artifact["checkpoints"]`
  - `validator_script=artifact["validator_script"]`
  - `references={"logical": logical_artifact["graph"]}`
- logical and physical validator nodes may fall back to `state["author_output"]` only if `draft_artifact` is temporarily missing the checkpoint context during the same run; they must never read stage-specific field names

Do not carry `TGraphRuntime` or stage-specific checkpoint names forward.

- [ ] **Step 4: Re-run the stage-node tests**

Run: `python -m pytest tests/unit/stages/logical/test_author_node.py tests/unit/stages/logical/test_builder_node.py tests/unit/stages/logical/test_logical_validator_node.py tests/unit/stages/physical/test_physical_author_node.py tests/unit/stages/physical/test_physical_builder_node.py tests/unit/stages/physical/test_physical_validator_node.py -q`

Expected: PASS.

- [ ] **Step 5: Commit node/schema rewiring**

```bash
git add src/trace/stages/logical/nodes src/trace/stages/physical/nodes tests/unit/stages/logical tests/unit/stages/physical
git commit -m "refactor: migrate trace stage nodes to standalone graph artifacts"
```

### Task 7: Replace `BoundTGraphTools` with thin standalone repair tooling and update prompts

**Files:**
- Create: `src/trace/stages/repair_tools.py`
- Create: `src/trace/stages/prompt_contracts.py`
- Modify: `src/trace/stages/logical/nodes/repair.py`
- Modify: `src/trace/stages/physical/nodes/repair.py`
- Modify: `src/trace/stages/logical/nodes/author.py`
- Modify: `src/trace/stages/logical/nodes/builder.py`
- Modify: `src/trace/stages/physical/nodes/author.py`
- Modify: `src/trace/stages/physical/nodes/builder.py`
- Modify: `src/trace/stages/logical/prompts/author.md`
- Modify: `src/trace/stages/logical/prompts/builder.md`
- Modify: `src/trace/stages/logical/prompts/repair.md`
- Modify: `src/trace/stages/physical/prompts/author.md`
- Modify: `src/trace/stages/physical/prompts/builder.md`
- Modify: `src/trace/stages/physical/prompts/repair.md`
- Modify: `tests/unit/stages/logical/test_repair_node.py`
- Modify: `tests/unit/stages/physical/test_physical_repair_node.py`
- Modify: `tests/unit/config/test_prompts.py`

- [ ] **Step 1: Write the failing repair/prompt tests**

Update repair-node tests so the tool constructor is no longer `BoundTGraphTools.from_json(graph_json, graph_field="tgraph_logical", checkpoints_field="logical_checkpoints")`. The new assertions should verify:

```python
assert captured["artifact"]["graph"]["stage"] == "logical"
assert captured["artifact"]["checkpoints"][0]["id"] == "cp1"
assert captured["artifact"]["validator_script"] is None


def test_physical_repair_validation_uses_logical_reference_graph() -> None:
    assert captured["validation_context"]["references"]["logical"]["stage"] == "logical"
    assert captured["validation_context"]["checkpoints"][0]["id"] == "pc1"
```

Update prompt tests to expect:

- `graph` instead of `tgraph_logical` / `tgraph_physical`
- `checkpoints` / `validator_script` instead of stage-specific names
- `stage` instead of `profile`
- batch patch protocol only; no `add_link`, `update_node`, or transaction terminology in the user-facing contract
- repair-node tool assertions are rewritten away from low-level graph mutation tools such as `add_link` and `update_node`; the allowed tool surface is `inspect_graph`, `apply_graph_patch`, `validate_graph`, `list_checkpoints`, `get_checkpoint`, `ensure_checkpoint`, `remove_checkpoint`, and `replace_validator_script`
- repair/author/builder nodes no longer import or mention `load_tgraph_contract_for`
- prompt examples and constraints no longer use old checkpoint vocabulary such as `connect_nodes`, `switch_has_subnet`, `node_interface_on_segment`, or `segment_id`; rewrite them to the new `assert_*` builtins and CIDR-centered args

- [ ] **Step 2: Run the repair/prompt tests**

Run: `python -m pytest tests/unit/stages/logical/test_repair_node.py tests/unit/stages/physical/test_physical_repair_node.py tests/unit/config/test_prompts.py -q`

Expected: FAIL because repair nodes and prompts still point at `BoundTGraphTools` and the old contract files.

- [ ] **Step 3: Implement shared repair tools**

Create `src/trace/stages/repair_tools.py` with a focused wrapper API:

```python
class StageRepairTools:
    def __init__(self, artifact: StageArtifact, *, logical_reference_graph: TGraph | None = None) -> None
    def as_agent_tools(self) -> list[dict[str, Any]]
    def inspect_graph(self, view: str, **kwargs) -> dict[str, Any]
    def apply_graph_patch(self, patch_ops: list[dict[str, Any]], *, validate: bool = True) -> StageArtifact
    def validate_graph(self) -> ValidationReport
    def list_checkpoints(self) -> list[CheckpointSpec]
    def get_checkpoint(self, checkpoint_id: str) -> CheckpointSpec | None
    def ensure_checkpoint(self, checkpoint: CheckpointSpec) -> StageArtifact
    def remove_checkpoint(self, checkpoint_id: str) -> StageArtifact
    def replace_validator_script(self, script: str | None) -> StageArtifact
```

Rules:

- graph mutation path is batch patch only
- graph operations call standalone `tgraph.inspect_graph`, `tgraph.apply_patch`, and `tgraph.validate_graph`
- checkpoint/script edits modify TRACE stage artifact only
- `StageRepairTools.as_agent_tools()` must expose the exact tool-binding surface consumed by `role_client.invoke_agent(...)`; do not leave repair integration as plain methods with no adapter
- `StageRepairTools.validate_graph()` must build the same `ValidationContext` as the corresponding validator node; physical repair always passes `references={"logical": logical_reference_graph}` and `preserve_topology_from=logical_reference_graph`
- `src/trace/stages/prompt_contracts.py` replaces `trace.tools.tgraph.prompting.load_tgraph_contract_for` and exposes small helpers that read from `src/tgraph/agent/playbooks/capabilities.md`, `authoring.md`, `repair.md`, and `validation.md`
- prompt text must refer to standalone `tgraph` capability docs, not `src/trace/tools/tgraph/contract.md`

- [ ] **Step 4: Re-run the repair/prompt tests**

Run: `python -m pytest tests/unit/stages/logical/test_repair_node.py tests/unit/stages/physical/test_physical_repair_node.py tests/unit/config/test_prompts.py -q`

Expected: PASS.

- [ ] **Step 5: Commit repair-tool migration**

```bash
git add src/trace/stages/repair_tools.py src/trace/stages/prompt_contracts.py src/trace/stages/logical/nodes/author.py src/trace/stages/logical/nodes/builder.py src/trace/stages/logical/nodes/repair.py src/trace/stages/physical/nodes/author.py src/trace/stages/physical/nodes/builder.py src/trace/stages/physical/nodes/repair.py src/trace/stages/logical/prompts src/trace/stages/physical/prompts tests/unit/stages/logical/test_repair_node.py tests/unit/stages/physical/test_physical_repair_node.py tests/unit/config/test_prompts.py
git commit -m "refactor: migrate trace repair flow to standalone tgraph tools"
```

## Chunk 4: Migrate Skill Scripts And Remove The Legacy TRACE TGraph Package

### Task 8: Update skill scripts and their backend to the new artifact shape

**Files:**
- Modify: `skills/tgraph-iac/SKILL.md`
- Modify: `skills/tgraph-iac/scripts/trace_backend.py`
- Modify: `skills/tgraph-iac/scripts/tgraph_apply_patch.py`
- Modify: `skills/tgraph-iac/scripts/tgraph_inspect.py`
- Modify: `skills/tgraph-iac/scripts/tgraph_validate.py`
- Modify: `skills/tgraph-iac/scripts/tgraph_export.py`
- Modify: `skills/tgraph-iac/references/patch-protocol.md`
- Modify: `skills/tgraph-iac/references/tgraph-ir.md`
- Modify: `skills/tgraph-iac/references/validation.md`
- Modify: `skills/tgraph-iac/references/agent-workflows.md`
- Modify: `tests/unit/skills/test_tgraph_iac_scripts.py`
- Modify: `tests/unit/skills/test_tgraph_iac_trace_backend.py`

- [ ] **Step 1: Write the failing skill-script tests**

Update script tests so fixtures use:

```python
artifact = {
    "graph": {"stage": "logical", "nodes": [], "links": []},
    "checkpoints": [],
    "validator_script": None,
}
```

Add expectations:

- `tgraph_apply_patch.py` writes `artifact["graph"]`
- `tgraph_apply_patch.py` can upsert/remove artifact-level `checkpoints` and replace/remove `validator_script`
- `tgraph_validate.py` passes `checkpoints` and `validator_script` into standalone `ValidationContext`
- `tgraph_validate.py --stage physical` passes the logical reference graph and `required_node_fields=["image", "flavor"]` into `ValidationContext`
- `tgraph_export.py --target tgraph-json` exports `artifact["graph"]`
- `trace_backend.py` infers stage from `artifact["graph"]["stage"]`, not from field names

Add one explicit patch-script test:

```python
def test_apply_patch_updates_checkpoint_and_validator_script_sections(tmp_path: Path) -> None:
    artifact_path = tmp_path / "logical_artifact.json"
    artifact_path.write_text(json.dumps({
        "graph": {"stage": "logical", "nodes": [], "links": []},
        "checkpoints": [],
        "validator_script": None,
    }), encoding="utf-8")

    run_script(
        "tgraph_apply_patch.py",
        artifact_path,
        checkpoint_patch={"upserts": [{"id": "cp1", "func": "assert_graph", "args": {"stage": "logical"}}]},
        validator_patch={"replace": "def check_ok(tgraph, **kwargs): return []"},
    )

    written = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert written["checkpoints"][0]["id"] == "cp1"
    assert "def check_ok" in written["validator_script"]


def test_validate_physical_artifact_passes_logical_reference_graph(tmp_path: Path) -> None:
    logical_artifact = {
        "graph": {"stage": "logical", "nodes": [{"id": "R1", "type": "router", "label": "R1", "ports": []}], "links": []},
        "checkpoints": [],
        "validator_script": None,
    }
    physical_artifact = {
        "graph": {"stage": "physical", "nodes": [{"id": "R1", "type": "router", "label": "R1", "ports": [], "image": None, "flavor": None}], "links": []},
        "checkpoints": [{"id": "pc1", "func": "assert_graph", "args": {"preserve_topology_from": "logical"}}],
        "validator_script": None,
    }
    result = run_validate_script(stage="physical", artifact=physical_artifact, logical_artifact=logical_artifact)
    assert result["context"]["references"]["logical"]["stage"] == "logical"
    assert result["context"]["preserve_topology_from"]["stage"] == "logical"
    assert result["context"]["required_node_fields"] == ["image", "flavor"]
```

- [ ] **Step 2: Run the skill-script tests**

Run: `python -m pytest tests/unit/skills/test_tgraph_iac_scripts.py tests/unit/skills/test_tgraph_iac_trace_backend.py -q`

Expected: FAIL because scripts still route through `trace.tools.tgraph.patch` and stage-specific field tables.

- [ ] **Step 3: Implement the script migration**

Implementation rules:

- `skills/tgraph-iac/SKILL.md` and the reference docs it points to must be updated in the same chunk so the skill no longer tells agents to use stale patch/checkpoint vocabulary
- `trace_backend.py` should expose helper functions around `graph/checkpoints/validator_script`
- `trace_backend.py` must define one explicit physical-validation contract: when `stage == "physical"`, the caller supplies `--logical-artifact <path>` (or the backend helper equivalent) and the backend loads that artifact's `graph` as `logical_reference_graph`
- `tgraph_apply_patch.py` should:
  - load the stage artifact
  - apply graph patch via standalone `tgraph.apply_patch`
  - apply artifact-layer checkpoint patch helpers whenever the request includes `checkpoint_patch`
  - apply artifact-layer validator-script replacement/removal whenever the request includes `validator_patch`
  - persist the updated artifact
- `tgraph_validate.py` must accept `--logical-artifact <path>` for physical-stage validation and call standalone `validate_graph(graph, context=ValidationContext(checkpoints=artifact["checkpoints"], validator_script=artifact["validator_script"], references={"logical": logical_reference_graph} if stage == "physical" else {}, preserve_topology_from=logical_reference_graph if stage == "physical" else None, required_node_fields=["image", "flavor"] if stage == "physical" else []))`
- `tgraph_inspect.py` should inspect `artifact["graph"]`
- `tgraph_export.py` should export the graph field directly for `tgraph-json`
- the skill reference docs must use the new checkpoint vocabulary (`assert_*` builtins, CIDR-centered args, batch patch envelope) and must not retain examples like `connect_nodes` or `segment_id`

- [ ] **Step 4: Re-run the skill-script tests**

Run: `python -m pytest tests/unit/skills/test_tgraph_iac_scripts.py tests/unit/skills/test_tgraph_iac_trace_backend.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the skill migration**

```bash
git add skills/tgraph-iac/SKILL.md skills/tgraph-iac/scripts skills/tgraph-iac/references tests/unit/skills/test_tgraph_iac_scripts.py tests/unit/skills/test_tgraph_iac_trace_backend.py
git commit -m "refactor: migrate tgraph skill scripts to standalone artifacts"
```

### Task 9: Delete the old TRACE-owned TGraph package and remove all remaining references

**Files:**
- Delete: `src/trace/tools/tgraph/**`
- Delete: `tests/unit/tools/tgraph/**`
- Modify only if grep still finds legacy names in files already touched by Tasks 4-8:
  - `src/trace/stages/common.py`
  - `src/trace/stages/logical/schemas.py`
  - `src/trace/stages/physical/schemas.py`
  - `src/trace/stages/logical/nodes/*.py`
  - `src/trace/stages/physical/nodes/*.py`
  - `src/trace/stages/logical/prompts/*.md`
  - `src/trace/stages/physical/prompts/*.md`
  - `skills/tgraph-iac/scripts/*.py`
  - `skills/tgraph-iac/references/tgraph-ir.md`
  - `skills/tgraph-iac/references/patch-protocol.md`
  - `skills/tgraph-iac/references/validation.md`
  - `skills/tgraph-iac/references/agent-workflows.md`
  - `tests/unit/storage/test_run_storage.py`
  - `tests/unit/runtime/test_reducers.py`
  - `tests/integration/test_runtime_pipeline.py`

- [ ] **Step 1: Write the failing “no legacy references” check**

Use repo-wide grep as the test:

Run:

```bash
rg -n "trace\\.tools\\.tgraph|TGraphJSON|TGraphRuntime|tgraph_logical|tgraph_physical|logical_checkpoints|physical_checkpoints|logical_validator_script|physical_validator_script|profile\\b|connect_nodes|switch_has_subnet|node_interface_on_segment|segment_id" src skills/tgraph-iac/scripts skills/tgraph-iac/references
rg -n "\"(segment|software|packages|zone)\"\\s*:" src/tgraph/core src/tgraph/operations/validate src/trace/stages skills/tgraph-iac/scripts
```

Expected:

- first grep finds matches in stage code, skill references, prompts, and the legacy package files
- second grep finds no forbidden higher-level fields being modeled in IR/helper code; if it does, fix it before deleting the legacy package

- [ ] **Step 2: Remove the legacy package and rewrite only known leftover call sites**

Delete the legacy files listed in the file map. Then migrate or delete old tests:

- move any still-relevant behavior assertions into `tests/unit/tgraph/*`, `tests/unit/stages/*`, or `tests/unit/skills/*`
- delete tests that existed only to preserve the old compatibility layer
- do not introduce new scope here; if grep still shows active-code hits after deleting the package, fix them only in the exact files listed above and stop if a new unexpected file appears

- [ ] **Step 3: Re-run the grep check**

Run:

```bash
rg -n "trace\\.tools\\.tgraph|TGraphJSON|TGraphRuntime|tgraph_logical|tgraph_physical|logical_checkpoints|physical_checkpoints|logical_validator_script|physical_validator_script|profile\\b|connect_nodes|switch_has_subnet|node_interface_on_segment|segment_id" src skills/tgraph-iac/scripts skills/tgraph-iac/references
rg -n "\"(segment|software|packages|zone)\"\\s*:" src/tgraph/core src/tgraph/operations/validate src/trace/stages skills/tgraph-iac/scripts
```

Expected:

- first grep returns no output
- second grep returns no output

- [ ] **Step 4: Commit legacy removal**

```bash
git add -- src/trace/tools/tgraph tests/unit/tools/tgraph src/trace/stages/common.py src/trace/stages/logical/schemas.py src/trace/stages/physical/schemas.py src/trace/stages/logical/nodes src/trace/stages/physical/nodes src/trace/stages/logical/prompts src/trace/stages/physical/prompts skills/tgraph-iac/scripts skills/tgraph-iac/references skills/tgraph-iac/SKILL.md tests/unit/storage/test_run_storage.py tests/unit/runtime/test_reducers.py tests/integration/test_runtime_pipeline.py
git commit -m "refactor: remove legacy trace tgraph compatibility layer"
```

## Chunk 5: Close The Loop With Integration, Storage, And Full Verification

### Task 10: Update end-to-end tests and run the full suite

**Files:**
- Modify: `tests/integration/test_runtime_pipeline.py`

Storage, reducer, prompt, and skill tests are rerun-only in this chunk; their actual edits are owned by earlier tasks.

- [ ] **Step 1: Rewrite the integration fixtures and expectations**

Rewrite the integration fixtures so every stage artifact uses the new shared shape. Replace:

```python
"logical_checkpoints": [{"id": "cp_router", "func": "assert_node", "args": {"node": "R1", "exists": True}}]
"logical_validator_script": None
"tgraph_logical": {"profile": "logical.v1", "nodes": [], "links": []}
"physical_checkpoints": [{"id": "pc_topology", "func": "assert_graph", "args": {"preserve_topology_from": "logical"}}]
"physical_validator_script": None
"tgraph_physical": {"profile": "taal.default.v1", "nodes": [], "links": []}
```

to:

```python
"checkpoints": [{"id": "cp_router", "func": "assert_node", "args": {"node": "R1", "exists": True}}]
"validator_script": None
"graph": {"stage": "logical", "nodes": [], "links": []}
```

and for physical fixtures:

```python
"checkpoints": [{"id": "pc_topology", "func": "assert_graph", "args": {"preserve_topology_from": "logical"}}]
"validator_script": None
"graph": {"stage": "physical", "nodes": [], "links": []}
```

Also update the assertions so they explicitly prove:

- `set(result["artifacts"]["logical"]) == {"graph", "checkpoints", "validator_script"}`
- `set(result["artifacts"]["physical"]) == {"graph", "checkpoints", "validator_script"}`
- `result["artifacts"]["logical"]["graph"]["stage"] == "logical"`
- `result["artifacts"]["physical"]["graph"]["stage"] == "physical"`
- `result["artifacts"]["physical"]["graph"]["links"] == result["artifacts"]["logical"]["graph"]["links"]`
- repair transcript/tool payloads use batch graph patch actions such as `apply_graph_patch` with a list of patch ops, not legacy one-op commands such as `add_link` or `update_node`

- [ ] **Step 2: Run the integration test file**

Run: `python -m pytest tests/integration/test_runtime_pipeline.py -q`

Expected: PASS.

- [ ] **Step 3: Run the focused unit suites that cover the migration surface**

Run: `python -m pytest tests/unit/tgraph tests/unit/stages tests/unit/skills tests/unit/config/test_prompts.py tests/unit/storage/test_run_storage.py tests/unit/runtime/test_reducers.py -q`

Expected: PASS.

- [ ] **Step 4: Run the full test suite**

Run: `python -m pytest -q`

Expected: PASS with no failures.

- [ ] **Step 5: Run final sanity greps**

Run:

```bash
rg -n "trace\\.tools\\.tgraph|TGraphJSON|TGraphRuntime|tgraph_logical|tgraph_physical|logical_checkpoints|physical_checkpoints|logical_validator_script|physical_validator_script|profile\\b|connect_nodes|switch_has_subnet|node_interface_on_segment|segment_id" src skills/tgraph-iac/scripts skills/tgraph-iac/references
rg -n "\"(segment|software|packages|zone)\"\\s*:" src/tgraph/core src/tgraph/operations/validate src/trace/stages skills/tgraph-iac/scripts
```

Expected:

- first grep returns no active-code or active-skill-reference hits; if a historical design doc still mentions old names, keep it outside the active implementation surface
- second grep returns no forbidden higher-level fields in IR/helper code paths; capability-contract docs and tests are intentionally excluded because they discuss those terms as unsupported

- [ ] **Step 6: Commit the final migration pass**

```bash
git add -- tests/integration/test_runtime_pipeline.py
git commit -m "test: verify hard migration to standalone tgraph"
```

- [ ] **Step 7: Prepare execution handoff**

Capture:

- final `python -m pytest -q` result
- final grep outputs
- a short migration summary listing:
  - new stage artifact shape
  - standalone TGraph F4 surface
  - deleted legacy package/modules
  - any follow-up work intentionally deferred (real Terraform/Pulumi emitters)
