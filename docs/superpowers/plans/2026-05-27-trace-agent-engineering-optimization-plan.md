# TRACE Agent Engineering Optimization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trim TRACE agent prompts and tools, expose image catalog as agent tools, introduce ledger product-pointers and mutation-incrementality, converge on LangGraph 1.x native features (reducer, Command, SqliteSaver), and add a ground-escalation feedback channel — all of the eight problems observed in `runs/demo-007`.

**Architecture:** Four sequential PRs / chunks. PR1 (Chunk 1) is pure surface integrity: prompts, tool returns, file filtering, image catalog tools — zero runtime state-machine changes. PR2 (Chunk 2) introduces a deterministic produced-files ledger and a `diff` inspect view, paving the way for mutation incrementality. PR3 (Chunk 3) converges the runtime onto LangGraph 1.x: list reducers, Command-based routing, ChatOpenAI caching. PR4 (Chunk 4) layers in SqliteSaver checkpointing with a clear RunStorage dual-track contract, plus the escalation channel back to `ground.author`.

**Tech Stack:** Python 3.10, Pydantic v2, LangGraph 1.1.x (`StateGraph`, `create_react_agent`, `Command`, `SqliteSaver`), LangChain 1.2.x (`@tool`, `ChatOpenAI`), pytest, AST-based mutation sandboxing.

---

## Reference Spec

- `docs/superpowers/specs/2026-05-27-trace-agent-engineering-optimization-design.md`

The spec is the source of truth for design intent. This plan operationalizes it into bite-sized TDD tasks.

## Glossary For This Plan

- **agent role** = a tool-using react agent (logical / physical author, builder, repair). Final-message-as-action-summary constraint applies here.
- **structured role** = a `with_structured_output` JSON-only role (ground author, ground evaluator). Final-message constraint does NOT apply (would contradict "Return only a JSON object").
- **physical scope tools** = `find_images` / `get_image`. Only wired into physical agent tool lists (per spec).
- **stage tools (`StageRepairTools`)** = shared by logical and physical builder/repair. Default surface is stage-agnostic; an `include_image_tools=False` flag lets physical callers opt in.

## File Structure Map

### Chunk 1 — PR1 prompt and tool surface cleanup

Source files (logic change):

- `src/trace/stages/support_files.py` — add `_FilterParams` mixin, `filtered_view` helper.
- `src/trace/stages/repair_tools.py` — add `MutationSummary` model and `_derive_op_counts`; extend `_ReadSupportFileInput` with `_FilterParams`; add `_FindImagesInput` / `_GetImageInput`; add `list_support_files`; `as_agent_tools(include_image_tools=False)` flag; pass `include_graph` through `_ExecuteMutationFileInput`.
- `src/trace/stages/logical/nodes/builder.py` — drop `graph_summary` injection + `_graph_summary` helper.
- `src/trace/stages/physical/nodes/builder.py` — drop `graph_summary` + `_graph_summary`; remove `image_catalog` key from `system_context_sections`; build `StageRepairTools` with `include_image_tools=True`.
- `src/trace/stages/physical/nodes/author.py` — drop `graph_summary` + `_graph_summary`; remove `image_catalog` from `system_context_sections`; `PhysicalAuthorTools.as_agent_tools()` adds `find_images` / `get_image`; `read_constraint_file` closure uses `_FilterParams`.
- `src/trace/stages/physical/nodes/repair.py` — drop the `Image catalog for this repair round:` system message and the `image_catalog` parameter of `_build_repair_messages`; build `StageRepairTools` with `include_image_tools=True`.
- `src/trace/stages/logical/nodes/author.py` — extend `read_constraint_file` closure with `_FilterParams`.
- `src/trace/stages/logical/prompts/author.md` — strip `## TGraph Check API` block.
- `src/trace/stages/logical/prompts/builder.md` — strip `## Mutation Contract` API list; rewrite the segment-vs-IR contradiction.
- `src/trace/stages/logical/prompts/repair.md` — strip `## Available Tools` API listing.
- `src/trace/stages/physical/prompts/author.md` — strip `## TGraph Check API`; add `## Kind→Tool Decision Table`.
- `src/trace/stages/physical/prompts/builder.md` — strip `## Mutation Contract` API list; add switch-iteration hint.
- `src/trace/stages/physical/prompts/repair.md` — strip `## Available Tools`.
- All six **agent role** prompts above — append final-message constraint.
- `src/trace/stages/ground/prompts/author.md` — UNCHANGED (structured role).
- `src/trace/stages/ground/prompts/evaluator.md` — UNCHANGED (structured role).
- `src/tgraph/agent/playbooks/authoring.md` — ADD a TGraph Check / Editor API block that **explicitly** describes `check_interface` and `ensure_interface` with `segment` required and clarifies "`segment` is the neighboring switch / segment-carrier node id, not an IR field".
- `src/tgraph/agent/playbooks/capabilities.md` — at line 29 remove the `segment` token from the "unsupported IR fields" enumeration (because `segment` is a function parameter, not an IR field; keep the others: `software`, `packages`, `zone`, `firewall_rules`).
- `src/tgraph/agent/docs/tgraph_check_api.md` — update `check_interface` signature line to call out `segment` required; add a one-line note on parameter-vs-IR-field.
- `src/tgraph/agent/docs/tgraph_editor_api.md` — same for `ensure_interface`.
- `src/tgraph/agent/playbooks/repair.md` — add line: "When choosing images, use `find_images` / `get_image` agent tools. Do not recall `image_id` from memory."

Existing tests that MUST be updated (logic changes break them):

- `tests/unit/stages/physical/test_physical_author_node.py` L42-43: `[image_catalog]` / `img_pfsense` assertions → replace with negative assertions + assert `find_images` / `get_image` in `tool_names`.
- `tests/unit/stages/physical/test_physical_builder_node.py` L84-98: exact `tool_names == [...]` + `[image_catalog]` / `img_pfsense` / `[graph_summary]` → replace with set-based contains assertions (no `[graph_summary]`, no `[image_catalog]`, includes `find_images`/`get_image`).
- `tests/unit/stages/physical/test_physical_repair_node.py` L71-78 + L131-132: exact `tool_names == [...]` + image_catalog assertions → replace with set-based assertions; assert `Image catalog for this repair round:` NOT present.
- `tests/unit/stages/logical/test_builder_node.py` L74-88: exact `tool_names == [...]` + `[graph_summary]` → replace with set-based assertions (no `find_images` in logical), no `[graph_summary]`.
- `tests/unit/stages/logical/test_author_node.py` and `test_repair_node.py`: any `tool_names == [...]` exact assertion → switch to set-based contains.

New tests:

- `tests/unit/stages/test_repair_tools_summary.py` — MutationSummary + `_derive_op_counts` + `include_graph` flag.
- `tests/unit/stages/test_support_files_filtered.py` — `filtered_view` and `_FilterParams`.
- `tests/unit/stages/test_filtered_read_tools.py` — three-call-site filtered read integration.
- `tests/unit/stages/test_image_tools.py` — `find_images` / `get_image` tool wrappers (physical scope).
- `tests/unit/stages/test_image_tools_logical_scope.py` — assertion that logical `StageRepairTools.as_agent_tools()` does NOT expose `find_images` / `get_image` by default.
- `tests/unit/stages/test_prompts_surface.py` — no `tgraph.check_` / `tgraph.ensure_` / `tgraph.set_image` / `tgraph.set_flavor` listings in `src/trace/stages/*/prompts/*.md`; final-message constraint present in six agent prompts only; kind→tool table present; switch hint present; logical builder no longer forbids `segment` token.
- `tests/unit/tgraph/agent/test_playbook_segment.py` — playbook authoring marks `segment` required and clarifies parameter-vs-IR-field; capabilities no longer lists `segment` as unsupported IR field; repair playbook mentions `find_images` / `get_image`.

### Chunk 2 — PR2 ledger product-pointers and mutation incrementality

Source files (logic change):

- `src/trace/stages/repair_tools.py`
  - Constructor accepts `mutation_index_seed: int = 1`.
  - `_next_mutation_path` uses the seeded index.
  - `execute_mutation_file` lands a JSON snapshot to `<stage>/mutations/snapshots/attempt_N.json` (matching attempt id) on success and returns its path inside `summary.snapshot_path`.
  - `inspect_graph(view="diff", against="previous_attempt"|"logical_reference")` added as a method; `_InspectGraphToolInput` extended with `against: str | None`.
  - `MutationSummary` gains `snapshot_path: str | None` field.
- `src/tgraph/operations/inspect/diff.py` — new pure diff routine: `diff(current: TGraph, baseline: TGraph) -> dict`.
- `src/tgraph/operations/inspect/__init__.py` — register `view="diff"` dispatcher (delegates to `diff.py`).
- `src/trace/stages/logical/nodes/repair.py` — `_build_repair_ledger_entry` accepts `produced_files`; new `_derive_produced_files(attempted_actions)` helper; new `_summary_one_line(...)` helpers (mutation / checkpoint variants).
- `src/trace/stages/physical/nodes/repair.py` — same shape.
- `src/trace/stages/logical/nodes/builder.py`, `physical/nodes/builder.py` — pass `mutation_index_seed` derived from `len(state.get("repair_history", []))` to `StageRepairTools`; for builder this is always 0+1=1, so no-op in practice. Keeping the parameter set explicitly for clarity.
- `src/trace/stages/logical/nodes/repair.py`, `physical/nodes/repair.py` — pass `mutation_index_seed=len(state.get("repair_history", [])) + 1` to `StageRepairTools`; this ensures attempt indices strictly increase across reentries.
- `src/trace/stages/logical/prompts/builder.md`, `physical/prompts/builder.md` — replace "Write one complete mutation file" guidance with incremental + diff-inspect guidance; for builder also reference the prepare-seeded node inventory.
- `src/trace/stages/logical/prompts/repair.md`, `physical/prompts/repair.md` — replace mutation rewrite guidance with incremental guidance using `inspect_graph(view="diff", against="previous_attempt")`.

Tests (add):

- `tests/unit/tgraph/operations/test_inspect_diff.py` — `diff(current, baseline)` contract: added / removed / changed nodes, unchanged_count.
- `tests/unit/stages/test_inspect_graph_diff.py` — `StageRepairTools.inspect_graph(view="diff", against="previous_attempt")` and `against="logical_reference"`.
- `tests/unit/stages/test_mutation_snapshot.py` — `execute_mutation_file` writes the snapshot file; `MutationSummary.snapshot_path` populated.
- `tests/unit/stages/test_mutation_index_seed.py` — attempt N continues across `StageRepairTools` re-construction.
- `tests/unit/stages/test_produced_files.py` — `_derive_produced_files` path-precise pairing of `write_mutation_file` + `execute_mutation_file`, `summary_one_line` rendering.
- `tests/unit/stages/test_recent_repair_ledger.py` — ledger context includes `produced_files` with snapshot_path.

Tests (modify):

- `tests/unit/stages/logical/test_repair_node.py` — assert `repair_history[-1]["produced_files"]` non-empty when a mutation was written + executed.
- `tests/unit/stages/physical/test_physical_repair_node.py` — same.

### Chunk 3 — PR3 LangGraph native convergence

Source files (logic change):

- `src/trace/runtime/engine.py` — `RunState.events` becomes `Annotated[list[dict], operator.add]`; new field `escalation_history: Annotated[list[dict], operator.add]` (default `[]`); `_merge_stage_result` and `_merge_stage_exception` return partial updates instead of calling `merge_run_state` for list fields; `_finalize` returns partial.
- `src/trace/runtime/reducers.py` — `merge_run_state` drops the manual `events` list concat (now handled by reducer); keep `_merge_dict` for non-reducer dict fields.
- `src/trace/runtime/role_client.py` — `_chat_openai_cache` keyed by `(role_name, model, temperature, base_url)`; rename `max_tool_calls` → `max_react_steps` everywhere in this module (with backwards-compatible alias for one PR); compute `max_steps` from `max_react_steps` and pass to `create_react_agent` (or via custom `should_continue` if `max_steps` isn't supported in the pinned langgraph version — Chunk plan documents both branches).
- `src/trace/stages/ground/state.py`, `logical/state.py`, `physical/state.py` — `events`, `repair_history`, `retry_history` annotated with `operator.add`; remove `next_action` field.
- `src/trace/stages/ground/nodes/evaluator.py`, `logical/nodes/validator.py`, `physical/nodes/validator.py` — return `Command(goto=..., update={...})` rather than mutating `state["next_action"]`.
- `src/trace/stages/ground/__init__.py`, `logical/__init__.py`, `physical/__init__.py` — drop `add_conditional_edges("validator", lambda state: state["next_action"], ...)`.
- All stage node files — replace `state["events"] = [*state.get("events", []), ...]`, `state["repair_history"] = [*prior_ledger, entry]`, `state["retry_history"] = [...]` with partial-update returns. (Detailed file list in tasks below.)

Tests (add):

- `tests/unit/runtime/test_reducers.py` — RunState events reducer accumulates across nodes.
- `tests/unit/runtime/test_role_client_cache.py` — `ChatOpenAI` instance reused across calls with same role tuple.
- `tests/unit/stages/test_validator_command.py` — validator nodes return `Command` with correct `goto`.
- `tests/unit/stages/test_evaluator_command.py` — ground evaluator returns `Command`.

Tests (modify):

- All stage validator tests — assert on `Command.goto` rather than `state["next_action"]`.
- Stage integration tests — events list accumulates via reducer (no explicit `[*...]` patterns needed in nodes).

### Chunk 4 — PR4 SqliteSaver checkpointer and escalation reverse channel

Source files (logic change):

- `pyproject.toml` — add `langgraph-checkpoint-sqlite` dependency.
- `.gitignore` — `runs/*/state.sqlite` and `runs/*/state.sqlite-*` (SQLite WAL/SHM sidecar files).
- `src/trace/runtime/engine.py` — wire `SqliteSaver` into `_build_run_graph`; pass `config={"configurable": {"thread_id": run_id}}` on `graph.invoke`; resume path prefers sqlite when present; route `escalated` stage results back to ground; bump `RunState` to include `escalation_history` (already added in Chunk 3 Task 3.1).
- `src/trace/runtime/escalation.py` (new) — `ESCALATION_TO_GROUND_KINDS` constant set; `extract_escalation_issues(report)` helper; `build_escalation_report(stage_id, report, partial_artifact, attempt)` helper.
- `src/trace/stages/ground/state.py` — fields `escalation_report: dict | None`, `unsolvable_notes: list[str]`.
- `src/trace/stages/ground/__init__.py` — `run_ground_stage` accepts `escalation_report: dict | None = None` kwarg; seeds state.
- `src/trace/stages/ground/nodes/author.py` — when `escalation_report` is present, prepend an `escalation_feedback` section in the author prompt context, reusing `feedback_revision` mode.
- `src/trace/stages/ground/nodes/evaluator.py` — surface unsolvable via `Command(goto=END, update={"status": "unsolvable", ...})` when `draft_artifact.unsolvable == True`.
- `src/trace/stages/ground/schemas.py` — `GroundDraftArtifact` gains optional `unsolvable: bool = False` and `unsolvable_reason: str | None = None`.
- `src/trace/stages/logical/__init__.py`, `physical/__init__.py` — add `escalate` terminal node that shapes stage return to `{status: "escalated", escalation_report, partial_artifact, ...}`.
- `src/trace/stages/logical/nodes/validator.py`, `physical/nodes/validator.py` — already Command-based after Chunk 3; add new escalation precedence branch.
- `src/trace/stages/common.py` — `require_stage_result` recognizes `status=="escalated"`; passes through `escalation_report` and `partial_artifact`.
- `README.md` — "从阶段恢复" section gains SqliteSaver + escalation paragraph.

Tests (add):

- `tests/unit/runtime/test_checkpointer.py` — sqlite file created post-run; resume picks up from sqlite if present; fork resume falls back to RunStorage.
- `tests/unit/runtime/test_escalation_routing.py` — engine routes escalate → ground; counter cap at 2 → failed.
- `tests/unit/stages/test_validator_escalation.py` — validator returns `Command(goto="escalate")` for white-list kinds; precedence: max_attempts > escalate > repair.
- `tests/unit/stages/test_ground_escalation_mode.py` — author_node accepts escalation context; evaluator surfaces `Command(goto=END, update={"status": "unsolvable"})` when unsolvable.
- `tests/integration/test_escalation_loop.py` — full loop with synthesized constraint conflict.

Tests (modify):

- `tests/integration/test_runtime_pipeline.py` — assert `runs/<run_id>/state.sqlite` exists.
- Existing validator tests — extend with escalation branch coverage.

---

## Chunk 1: PR1 — Prompt And Tool Surface Cleanup

This chunk produces working software on its own. After PR1 merges, the agent's prompt/tool surface is leaner; the runtime state machine is unchanged.

**Branch / commit cadence:** ~14 commits, one per task. Final commit re-runs full pytest + demo smoke.

### Task 1.1: Add `MutationSummary` schema and shared `_derive_op_counts` helper

**Files:**
- Modify: `src/trace/stages/repair_tools.py`
- Create test: `tests/unit/stages/test_repair_tools_summary.py`

- [ ] **Step 1: Write failing tests for MutationSummary derivation**

Create `tests/unit/stages/test_repair_tools_summary.py`:

```python
from trace.stages.repair_tools import MutationSummary, _derive_op_counts


def test_derive_op_counts_aggregates_by_op_name():
    operations = [
        {"op": "ensure_direct_link", "link": "A-B-1", "nodes": ["A", "B"], "link_key": "1"},
        {"op": "ensure_direct_link", "link": "B-C-1", "nodes": ["B", "C"], "link_key": "1"},
        {"op": "set_image", "node": "A", "image_id": "img_pfsense"},
    ]
    assert _derive_op_counts(operations) == {"ensure_direct_link": 2, "set_image": 1}


def test_mutation_summary_affected_node_ids_from_scalar_and_list_fields():
    operations = [
        {"op": "ensure_node", "node": "A"},
        {"op": "ensure_direct_link", "link": "A-B-1", "nodes": ["A", "B"]},
        {"op": "set_image", "node": "B", "image_id": "img_pfsense"},
        {"op": "ensure_interface", "node": "C", "segment": "B", "cidr": "10.0.0.0/24", "ip": None},
        {"op": "remove_links", "links_removed": ["X-Y-1"], "ports_removed": ["X._Y-1", "Y._X-1"]},
    ]
    summary = MutationSummary.from_operations(stage="logical", node_count=10, link_count=8, operations=operations)
    assert summary.affected_node_ids == ["A", "B", "C", "X", "Y"]
    assert summary.affected_link_ids == ["A-B-1", "X-Y-1"]
    assert summary.op_counts == {
        "ensure_node": 1,
        "ensure_direct_link": 1,
        "set_image": 1,
        "ensure_interface": 1,
        "remove_links": 1,
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/stages/test_repair_tools_summary.py -v`
Expected: FAIL with `ImportError: cannot import name 'MutationSummary'` and `_derive_op_counts`.

- [ ] **Step 3: Implement MutationSummary and helper**

Add to `src/trace/stages/repair_tools.py` (top-level, before `StageRepairTools`):

```python
from collections import Counter


class MutationSummary(BaseModel):
    stage: str
    node_count: int
    link_count: int
    affected_node_ids: list[str]
    affected_link_ids: list[str]
    op_counts: dict[str, int]

    @classmethod
    def from_operations(
        cls,
        *,
        stage: str,
        node_count: int,
        link_count: int,
        operations: list[dict[str, Any]],
    ) -> "MutationSummary":
        node_ids: set[str] = set()
        link_ids: set[str] = set()
        for op in operations:
            if isinstance(op.get("node"), str):
                node_ids.add(op["node"])
            if isinstance(op.get("nodes"), list):
                node_ids.update(item for item in op["nodes"] if isinstance(item, str))
            if isinstance(op.get("segment"), str):
                node_ids.add(op["segment"])
            if isinstance(op.get("link"), str):
                link_ids.add(op["link"])
            if isinstance(op.get("links_removed"), list):
                link_ids.update(item for item in op["links_removed"] if isinstance(item, str))
            if isinstance(op.get("ports_removed"), list):
                for token in op["ports_removed"]:
                    if not isinstance(token, str):
                        continue
                    node_part = token.split(".", 1)[0]
                    if node_part:
                        node_ids.add(node_part)
        return cls(
            stage=stage,
            node_count=node_count,
            link_count=link_count,
            affected_node_ids=sorted(node_ids),
            affected_link_ids=sorted(link_ids),
            op_counts=_derive_op_counts(operations),
        )


def _derive_op_counts(operations: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(op.get("op", "") for op in operations if op.get("op")))
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/stages/test_repair_tools_summary.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/stages/test_repair_tools_summary.py src/trace/stages/repair_tools.py
git commit -m "feat(repair_tools): add MutationSummary schema and op_counts helper"
```

### Task 1.2: Slim `execute_mutation_file` return; add `include_graph` flag

**Files:**
- Modify: `src/trace/stages/repair_tools.py`
- Modify: `tests/unit/stages/test_repair_tools_summary.py` (extend)
- Existing tests asserting `result["graph"]` will be updated in their own task (1.3 and 1.9).

- [ ] **Step 1: Extend tests for new return contract**

Append to `tests/unit/stages/test_repair_tools_summary.py`:

```python
from trace.stages.repair_tools import StageRepairTools


def _seed_logical_graph_dict() -> dict:
    return {
        "stage": "logical",
        "nodes": [
            {"id": "SW_DMZ", "type": "switch", "label": "SW_DMZ", "ports": []},
        ],
        "links": [],
    }


def test_execute_mutation_file_returns_summary_only_by_default(tmp_path):
    artifact = {"graph": _seed_logical_graph_dict(), "constraint_files": {}, "checkpoint_files": {}}
    tools = StageRepairTools(artifact, support_file_root=str(tmp_path))
    write = tools.write_mutation_file(
        content="def mutate(tgraph):\n    tgraph.ensure_subnet('SW_DMZ', cidr='10.10.10.0/24')\n",
        path="logical/mutations/test.py",
    )
    result = tools.execute_mutation_file(path=write["path"], validate=False)
    assert result["ok"] is True
    assert "summary" in result
    assert "graph" not in result
    assert result["summary"]["op_counts"] == {"ensure_subnet": 1}


def test_execute_mutation_file_includes_graph_when_requested(tmp_path):
    artifact = {"graph": _seed_logical_graph_dict(), "constraint_files": {}, "checkpoint_files": {}}
    tools = StageRepairTools(artifact, support_file_root=str(tmp_path))
    write = tools.write_mutation_file(
        content="def mutate(tgraph):\n    tgraph.ensure_subnet('SW_DMZ', cidr='10.10.10.0/24')\n",
        path="logical/mutations/test.py",
    )
    result = tools.execute_mutation_file(path=write["path"], validate=False, include_graph=True)
    assert "graph" in result
    assert result["graph"]["stage"] == "logical"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/stages/test_repair_tools_summary.py -v`
Expected: FAIL — current implementation always returns `graph` and no `summary`.

- [ ] **Step 3: Modify `StageRepairTools.execute_mutation_file` signature and body**

```python
def execute_mutation_file(self, *, path: str, validate: bool = True, include_graph: bool = False) -> dict[str, Any]:
    normalized = _safe_relative_path(path)
    if normalized not in self._support_files:
        return {"ok": False, "error": {"message": f"support file not found: {normalized}"}}
    mutation_path = self._materialize_support_file(normalized)
    result = execute_mutation_file(
        self._graph_model(),
        mutation_path=mutation_path,
        validate=validate,
        validation_context=self._validation_context(),
    )
    operations = list(result.operations or [])
    if result.ok and result.graph is not None:
        self._artifact["graph"] = result.graph.model_dump(mode="json")
    graph_model = self._graph_model()
    summary = MutationSummary.from_operations(
        stage=graph_model.stage,
        node_count=len(graph_model.nodes),
        link_count=len(graph_model.links),
        operations=operations,
    )
    payload: dict[str, Any] = {
        "ok": result.ok,
        "operations": [dict(op) for op in operations],
        "summary": summary.model_dump(mode="json"),
    }
    if not result.ok:
        payload["issues"] = [issue.model_dump(mode="json") for issue in result.issues]
    if include_graph and result.graph is not None:
        payload["graph"] = result.graph.model_dump(mode="json")
    return payload
```

- [ ] **Step 4: Update the tool wrapper to expose `include_graph`**

Inside `as_agent_tools(...)`, update `_ExecuteMutationFileInput`:

```python
class _ExecuteMutationFileInput(BaseModel):
    path: str
    run_validate: bool = Field(default=True, alias="validate")
    include_graph: bool = False
```

And the `execute_mutation_file_tool` closure:

```python
@tool("execute_mutation_file", args_schema=_ExecuteMutationFileInput)
def execute_mutation_file_tool(path: str, run_validate: bool = True, include_graph: bool = False) -> dict[str, Any]:
    """Execute a mutation file transactionally. Returns ok + operations + summary; pass include_graph=true to also receive the full graph."""
    return self.execute_mutation_file(path=path, validate=run_validate, include_graph=include_graph)
```

- [ ] **Step 5: Run focused tests to verify pass**

Run: `pytest tests/unit/stages/test_repair_tools_summary.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/trace/stages/repair_tools.py tests/unit/stages/test_repair_tools_summary.py
git commit -m "feat(repair_tools): slim execute_mutation_file return; add include_graph flag"
```

### Task 1.3: Remove `graph_summary` injection and update breaking tests

**Files:**
- Modify: `src/trace/stages/logical/nodes/builder.py` (drop `graph_summary` context key; drop `_graph_summary` helper)
- Modify: `src/trace/stages/physical/nodes/author.py` (same)
- Modify: `src/trace/stages/physical/nodes/builder.py` (same)
- Modify existing tests:
  - `tests/unit/stages/logical/test_builder_node.py` L88 (`assert "[graph_summary]" in human_content` → assert NOT present)
  - `tests/unit/stages/physical/test_physical_builder_node.py` L98 (same)
  - There is no `graph_summary` assertion in `test_physical_author_node.py`; verify with `rg "graph_summary" tests/unit/stages` before this task.

- [ ] **Step 1: Inventory current `graph_summary` references**

Run: `rg -n "graph_summary|_graph_summary" src/trace tests/unit`
Expected output: 3 source files (each with 2 hits: context key + helper definition) + 2 test files (each with 1 hit).

- [ ] **Step 2: Flip test assertions to negative**

In `tests/unit/stages/logical/test_builder_node.py` change L88 from
```python
assert "[graph_summary]" in human_content
```
to
```python
assert "[graph_summary]" not in human_content
```

Same flip in `tests/unit/stages/physical/test_physical_builder_node.py` L98.

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/stages/logical/test_builder_node.py tests/unit/stages/physical/test_physical_builder_node.py -v`
Expected: FAIL (graph_summary still being injected).

- [ ] **Step 4: Delete `graph_summary` from three source files**

In `src/trace/stages/logical/nodes/builder.py`:
- Remove `"graph_summary": _graph_summary(artifact.get("graph", {}))` from the `context_sections` dict.
- Remove the `def _graph_summary(...)` function definition.

In `src/trace/stages/physical/nodes/author.py`:
- Remove `"graph_summary": _graph_summary(state["logical_artifact"]["graph"])` from the `context_sections` dict.
- Remove the `def _graph_summary(...)` function definition.

In `src/trace/stages/physical/nodes/builder.py`:
- Remove `"graph_summary": _graph_summary(artifact.get("graph", {}))` from the `context_sections` dict.
- Remove the `def _graph_summary(...)` function definition.

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/unit/stages -v`
Expected: PASS for both builder tests; other unrelated stage tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add src/trace/stages/logical/nodes/builder.py src/trace/stages/physical/nodes/author.py src/trace/stages/physical/nodes/builder.py tests/unit/stages/logical/test_builder_node.py tests/unit/stages/physical/test_physical_builder_node.py
git commit -m "refactor(stages): drop graph_summary injection in builder/author contexts"
```

### Task 1.4: Add `_FilterParams` mixin and `filtered_view` helper

**Files:**
- Modify: `src/trace/stages/support_files.py`
- Create test: `tests/unit/stages/test_support_files_filtered.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/stages/test_support_files_filtered.py`:

```python
import json
from trace.stages.support_files import filtered_view, _FilterParams


SAMPLE_JSON = json.dumps({
    "lc1": {"statement": "SW_DMZ is subnet 10.10.10.0/24.", "kind": "logical.addressing.subnet"},
    "lc17": {"statement": "Routers require fixed IPv4.", "kind": "logical.custom"},
}, indent=2)


def test_filter_params_defaults_all_none():
    params = _FilterParams()
    assert params.match is None and params.keys is None and params.head_lines is None


def test_filtered_view_returns_full_content_when_no_filter():
    assert filtered_view(SAMPLE_JSON) == SAMPLE_JSON


def test_filtered_view_match_returns_line_window():
    out = filtered_view(SAMPLE_JSON, match="lc17")
    assert "lc17" in out
    assert "Routers require fixed IPv4" in out  # context +/-1 line
    assert "lc1\"" not in out  # other key not in window


def test_filtered_view_keys_returns_subdocument():
    out = filtered_view(SAMPLE_JSON, keys=["lc17"])
    parsed = json.loads(out)
    assert list(parsed.keys()) == ["lc17"]


def test_filtered_view_keys_ignored_when_not_json_object():
    plain = "line a\nline b\nline c\n"
    assert filtered_view(plain, keys=["a"]) == plain


def test_filtered_view_head_lines():
    plain = "\n".join(f"line {i}" for i in range(20))
    out = filtered_view(plain, head_lines=3)
    assert out.splitlines() == ["line 0", "line 1", "line 2"]


def test_filtered_view_priority_match_over_keys_over_head_lines():
    out = filtered_view(SAMPLE_JSON, match="lc17", keys=["lc1"], head_lines=2)
    assert "lc17" in out  # match wins
    assert "lc1\"" not in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/stages/test_support_files_filtered.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `_FilterParams` and `filtered_view`**

Append to `src/trace/stages/support_files.py`:

```python
from pydantic import BaseModel


class _FilterParams(BaseModel):
    match: str | None = None
    keys: list[str] | None = None
    head_lines: int | None = None


def filtered_view(
    content: str,
    *,
    match: str | None = None,
    keys: list[str] | None = None,
    head_lines: int | None = None,
) -> str:
    if match:
        return _match_window(content, needle=match, context=1)
    if keys:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return content
        if not isinstance(parsed, dict):
            return content
        subset = {key: parsed[key] for key in keys if key in parsed}
        return json.dumps(subset, indent=2, ensure_ascii=False)
    if head_lines is not None and head_lines >= 0:
        return "\n".join(content.splitlines()[:head_lines])
    return content


def _match_window(content: str, *, needle: str, context: int) -> str:
    lines = content.splitlines()
    selected: set[int] = set()
    for idx, line in enumerate(lines):
        if needle in line:
            start = max(0, idx - context)
            stop = min(len(lines), idx + context + 1)
            selected.update(range(start, stop))
    return "\n".join(lines[i] for i in sorted(selected))
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/stages/test_support_files_filtered.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/trace/stages/support_files.py tests/unit/stages/test_support_files_filtered.py
git commit -m "feat(support_files): add _FilterParams mixin and filtered_view helper"
```

### Task 1.5: Wire `_FilterParams` into `read_support_file` and both `read_constraint_file` tools

**Files:**
- Modify: `src/trace/stages/repair_tools.py` (`_ReadSupportFileInput` inherits `_FilterParams`; `read_support_file` method accepts filter kwargs; tool wrapper passes them)
- Modify: `src/trace/stages/logical/nodes/author.py` (`_ReadLogicalConstraintInput` inherits `_FilterParams`; closure uses `filtered_view`)
- Modify: `src/trace/stages/physical/nodes/author.py` (`_ReadPhysicalConstraintInput` inherits `_FilterParams`; closure uses `filtered_view`)
- Create test: `tests/unit/stages/test_filtered_read_tools.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/stages/test_filtered_read_tools.py
import json
from trace.stages.repair_tools import StageRepairTools


def _seed_artifact():
    return {
        "graph": {"stage": "logical", "nodes": [{"id": "A", "type": "computer", "label": "A", "ports": []}], "links": []},
        "constraint_files": {"logical": "ground/logical_constraints.json"},
        "checkpoint_files": {},
    }


def test_read_support_file_match():
    payload = {f"lc{i}": {"statement": f"lc{i}-stmt", "kind": "logical.custom"} for i in range(1, 18)}
    tools = StageRepairTools(_seed_artifact(), support_files={"ground/logical_constraints.json": json.dumps(payload, indent=2)})
    result = tools.read_support_file(path="ground/logical_constraints.json", match="lc17")
    assert result["ok"] is True
    assert "lc17" in result["content"]
    assert "lc16-stmt" not in result["content"]


def test_read_support_file_keys():
    payload = {"lc1": {"statement": "a"}, "lc17": {"statement": "z"}}
    tools = StageRepairTools(_seed_artifact(), support_files={"ground/logical_constraints.json": json.dumps(payload, indent=2)})
    result = tools.read_support_file(path="ground/logical_constraints.json", keys=["lc17"])
    parsed = json.loads(result["content"])
    assert parsed == {"lc17": {"statement": "z"}}


def test_read_support_file_tool_surface_accepts_filter_params():
    payload = {"lc1": {"statement": "a"}, "lc17": {"statement": "z"}}
    tools = StageRepairTools(_seed_artifact(), support_files={"ground/logical_constraints.json": json.dumps(payload, indent=2)})
    bound = {tool.name: tool for tool in tools.as_agent_tools()}
    result = bound["read_support_file"].invoke({"path": "ground/logical_constraints.json", "match": "lc17"})
    assert "lc17" in result["content"]


def test_logical_author_read_constraint_file_supports_filter():
    from trace.stages.logical.nodes.author import LogicalAuthorTools
    state = {
        "support_files": {
            "ground/logical_constraints.json": json.dumps(
                {"lc1": {"statement": "a"}, "lc17": {"statement": "z"}}, indent=2
            )
        }
    }
    tools = LogicalAuthorTools(state=state, logical_constraints=[{"id": "lc1"}, {"id": "lc17"}]).as_agent_tools()
    bound = {tool.name: tool for tool in tools}
    out = bound["read_constraint_file"].invoke({"path": "ground/logical_constraints.json", "keys": ["lc17"]})
    parsed = json.loads(out["content"])
    assert parsed == {"lc17": {"statement": "z"}}


def test_physical_author_read_constraint_file_supports_filter():
    from trace.stages.physical.nodes.author import PhysicalAuthorTools
    state = {
        "support_files": {
            "ground/physical_constraints.json": json.dumps(
                {"pc1": {"statement": "a"}, "pc2": {"statement": "z"}}, indent=2
            )
        }
    }
    tools = PhysicalAuthorTools(state=state, physical_constraints=[{"id": "pc1"}, {"id": "pc2"}]).as_agent_tools()
    bound = {tool.name: tool for tool in tools}
    out = bound["read_constraint_file"].invoke({"path": "ground/physical_constraints.json", "match": "pc2"})
    assert "pc2" in out["content"]
    assert "pc1\"" not in out["content"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/stages/test_filtered_read_tools.py -v`
Expected: FAIL — current tools don't accept filter kwargs.

- [ ] **Step 3: Update `_ReadSupportFileInput` and `read_support_file` in repair_tools**

In `repair_tools.py`:

```python
from trace.stages.support_files import _FilterParams, filtered_view


class _ReadSupportFileInput(_FilterParams):
    path: str


def read_support_file(
    self,
    path: str,
    *,
    match: str | None = None,
    keys: list[str] | None = None,
    head_lines: int | None = None,
) -> dict[str, Any]:
    normalized = _safe_relative_path(path)
    if normalized not in self._support_files:
        return {"ok": False, "error": {"message": f"support file not found: {normalized}"}}
    content = filtered_view(self._support_files[normalized], match=match, keys=keys, head_lines=head_lines)
    return {"ok": True, "path": normalized, "content": content}
```

Update the `read_support_file_tool` closure inside `as_agent_tools`:

```python
@tool("read_support_file", args_schema=_ReadSupportFileInput)
def read_support_file_tool(
    path: str,
    match: str | None = None,
    keys: list[str] | None = None,
    head_lines: int | None = None,
) -> dict[str, Any]:
    """Read a support file with optional substring match, JSON key filter, or head-lines window."""
    return self.read_support_file(path, match=match, keys=keys, head_lines=head_lines)
```

- [ ] **Step 4: Update logical author `read_constraint_file` closure**

In `src/trace/stages/logical/nodes/author.py`:

```python
from trace.stages.support_files import _FilterParams, filtered_view


class _ReadLogicalConstraintInput(_FilterParams):
    path: str = DEFAULT_CONSTRAINT_PATH


# inside as_agent_tools:
@tool("read_constraint_file", args_schema=_ReadLogicalConstraintInput)
def read_constraint_file_tool(
    path: str = DEFAULT_CONSTRAINT_PATH,
    match: str | None = None,
    keys: list[str] | None = None,
    head_lines: int | None = None,
) -> dict[str, Any]:
    """Read a logical constraint file with optional substring match, JSON key filter, or head-lines window."""
    content = (self._state.get("support_files") or {}).get(path)
    if content is None:
        return {"ok": False, "error": {"message": f"support file not found: {path}"}}
    return {"ok": True, "path": path, "content": filtered_view(content, match=match, keys=keys, head_lines=head_lines)}
```

- [ ] **Step 5: Update physical author `read_constraint_file` closure**

Same pattern in `src/trace/stages/physical/nodes/author.py` using `_ReadPhysicalConstraintInput(_FilterParams)` with `path: str = DEFAULT_CONSTRAINT_PATH` (this DEFAULT_CONSTRAINT_PATH points to physical constraints).

- [ ] **Step 6: Run tests to verify pass**

Run: `pytest tests/unit/stages/test_filtered_read_tools.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/trace/stages/repair_tools.py src/trace/stages/logical/nodes/author.py src/trace/stages/physical/nodes/author.py tests/unit/stages/test_filtered_read_tools.py
git commit -m "feat(stages): add match/keys/head_lines filtering to read_*_file tools"
```

### Task 1.6: Add `list_support_files` agent tool

**Files:**
- Modify: `src/trace/stages/repair_tools.py`
- Modify: `tests/unit/stages/test_filtered_read_tools.py` (extend)

- [ ] **Step 1: Write failing test for the new tool**

Append to `tests/unit/stages/test_filtered_read_tools.py`:

```python
def test_list_support_files_returns_sorted_paths():
    tools = StageRepairTools(
        _seed_artifact(),
        support_files={"logical/checkpoints.py": "", "ground/logical_constraints.json": "{}"},
    )
    assert tools.list_support_files() == {"paths": ["ground/logical_constraints.json", "logical/checkpoints.py"]}


def test_list_support_files_exposed_as_agent_tool():
    tools = StageRepairTools(_seed_artifact(), support_files={"logical/checkpoints.py": ""})
    bound = {tool.name: tool for tool in tools.as_agent_tools()}
    assert "list_support_files" in bound
    result = bound["list_support_files"].invoke({})
    assert "paths" in result
```

- [ ] **Step 2: Flip existing stage-repair `tool_names == [...]` assertion that will be broken by adding `list_support_files`**

In `tests/unit/stages/logical/test_repair_node.py` L67-74, replace:

```python
assert client.calls[0]["tool_names"] == [
    "inspect_graph",
    "read_support_file",
    "write_checkpoint_file",
    "write_mutation_file",
    "execute_mutation_file",
    "validate_graph",
]
```

with:

```python
tool_names = set(client.calls[0]["tool_names"])
assert {"inspect_graph", "read_support_file", "write_checkpoint_file", "write_mutation_file", "execute_mutation_file", "validate_graph", "list_support_files"}.issubset(tool_names)
assert "find_images" not in tool_names  # logical scope must not expose image tools
assert "get_image" not in tool_names
```

(The same shape exists in `tests/unit/stages/physical/test_physical_builder_node.py` and `test_physical_repair_node.py` and is handled by Task 1.8 because it adds `find_images` / `get_image`; flip those there. This Step 2 only handles the logical-side file.)

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/stages/test_filtered_read_tools.py tests/unit/stages/logical/test_repair_node.py -v`
Expected: FAIL (method / tool not present; logical repair test now expects `list_support_files` which doesn't exist yet).

- [ ] **Step 4: Implement `list_support_files` method and tool**

Add to `StageRepairTools`:

```python
def list_support_files(self) -> dict[str, Any]:
    return {"paths": sorted(self._support_files.keys())}
```

In `as_agent_tools(...)`:

```python
@tool("list_support_files")
def list_support_files_tool() -> dict[str, Any]:
    """List all support file paths currently accessible to the agent."""
    return self.list_support_files()
```

Append `list_support_files_tool` to the returned `tools` list (before image tools added in Task 1.7).

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/unit/stages -v`
Expected: PASS (this broader scope catches the logical repair file plus the new filtered_read tests).

- [ ] **Step 6: Commit**

```bash
git add src/trace/stages/repair_tools.py tests/unit/stages/test_filtered_read_tools.py tests/unit/stages/logical/test_repair_node.py
git commit -m "feat(repair_tools): expose list_support_files as agent tool"
```

### Task 1.7: Wire `find_images` / `get_image` as physical-scoped agent tools

**Files:**
- Modify: `src/trace/stages/repair_tools.py` (add `include_image_tools` flag in `as_agent_tools(...)`; add `_FindImagesInput` / `_GetImageInput`)
- Create test: `tests/unit/stages/test_image_tools.py`
- Create test: `tests/unit/stages/test_image_tools_logical_scope.py`

- [ ] **Step 1: Write failing tests for physical-scope opt-in**

`tests/unit/stages/test_image_tools.py`:

```python
from trace.stages.repair_tools import StageRepairTools


def _seed_physical_artifact():
    return {
        "graph": {
            "stage": "physical",
            "nodes": [
                {"id": "FIREWALL", "type": "computer", "label": "FIREWALL", "ports": [], "image": None, "flavor": None}
            ],
            "links": [],
        },
        "constraint_files": {},
        "checkpoint_files": {},
    }


def test_find_images_filters_by_role_when_opt_in():
    tools = StageRepairTools(_seed_physical_artifact()).as_agent_tools(include_image_tools=True)
    bound = {t.name: t for t in tools}
    result = bound["find_images"].invoke({"roles": ["firewall"]})
    ids = [item["image"]["id"] for item in result["images"]]
    assert "img_pfsense" in ids


def test_get_image_returns_image_record_when_opt_in():
    tools = StageRepairTools(_seed_physical_artifact()).as_agent_tools(include_image_tools=True)
    bound = {t.name: t for t in tools}
    result = bound["get_image"].invoke({"image_id": "img_pfsense"})
    assert result["image"]["id"] == "img_pfsense"
    assert result["default_flavor"]["vcpu"] == 2


def test_get_image_unknown_id_returns_error_when_opt_in():
    tools = StageRepairTools(_seed_physical_artifact()).as_agent_tools(include_image_tools=True)
    bound = {t.name: t for t in tools}
    result = bound["get_image"].invoke({"image_id": "img_nonexistent"})
    assert result["ok"] is False
    assert "unknown image" in result["error"]["message"].lower()
```

`tests/unit/stages/test_image_tools_logical_scope.py`:

```python
from trace.stages.repair_tools import StageRepairTools


def _seed_logical_artifact():
    return {
        "graph": {"stage": "logical", "nodes": [{"id": "A", "type": "computer", "label": "A", "ports": []}], "links": []},
        "constraint_files": {},
        "checkpoint_files": {},
    }


def test_logical_scope_does_not_expose_image_tools_by_default():
    tools = StageRepairTools(_seed_logical_artifact()).as_agent_tools()
    names = {tool.name for tool in tools}
    assert "find_images" not in names
    assert "get_image" not in names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/stages/test_image_tools.py tests/unit/stages/test_image_tools_logical_scope.py -v`
Expected: FAIL — flag not implemented; positive tests can't find tools.

- [ ] **Step 3: Implement `include_image_tools` flag and image tools**

In `repair_tools.py`:

```python
from trace.tools.images.catalog import find_images, get_image


class _FindImagesInput(BaseModel):
    query: str | None = None
    roles: list[str] | None = None
    node_type: str | None = None
    limit: int = 10


class _GetImageInput(BaseModel):
    image_id: str
```

Modify `as_agent_tools` signature:

```python
def as_agent_tools(self, *, include_checkpoint_tool: bool = True, include_image_tools: bool = False) -> list[Any]:
    # ... existing tool builders ...

    tools = [
        inspect_graph_tool,
        read_support_file_tool,
        write_mutation_file_tool,
        execute_mutation_file_tool,
        validate_graph_tool,
        list_support_files_tool,
    ]
    if include_checkpoint_tool:
        tools.insert(2, write_checkpoint_file_tool)
    if include_image_tools:
        @tool("find_images", args_schema=_FindImagesInput)
        def find_images_tool(
            query: str | None = None,
            roles: list[str] | None = None,
            node_type: str | None = None,
            limit: int = 10,
        ) -> dict[str, Any]:
            """Search the image catalog by free-text query, role list, or node type. Returns ranked candidate images with default_flavor."""
            return {"images": find_images(query=query, roles=roles, node_type=node_type, limit=limit)}

        @tool("get_image", args_schema=_GetImageInput)
        def get_image_tool(image_id: str) -> dict[str, Any]:
            """Look up a specific image_id in the catalog. Returns image, roles, node_types, aliases, default_flavor."""
            try:
                return get_image(image_id)
            except KeyError as exc:
                return {"ok": False, "error": {"message": str(exc)}}

        tools.extend([find_images_tool, get_image_tool])
    return tools
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/stages/test_image_tools.py tests/unit/stages/test_image_tools_logical_scope.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/trace/stages/repair_tools.py tests/unit/stages/test_image_tools.py tests/unit/stages/test_image_tools_logical_scope.py
git commit -m "feat(repair_tools): add physical-scoped find_images and get_image tools"
```

### Task 1.8: Wire image tools into `PhysicalAuthorTools.as_agent_tools` and physical builder/repair callsites

**Files:**
- Modify: `src/trace/stages/physical/nodes/author.py` (extend `PhysicalAuthorTools.as_agent_tools` with image tools)
- Modify: `src/trace/stages/physical/nodes/builder.py` (pass `include_image_tools=True` when constructing `StageRepairTools` agent tools)
- Modify: `src/trace/stages/physical/nodes/repair.py` (pass `include_image_tools=True`)
- Update tests:
  - `tests/unit/stages/physical/test_physical_author_node.py` — assert `find_images` / `get_image` in `tool_names`
  - `tests/unit/stages/physical/test_physical_builder_node.py` L84-91 — replace exact `tool_names == [...]` with set-based containment
  - `tests/unit/stages/physical/test_physical_repair_node.py` L71-78 — same

- [ ] **Step 1: Flip existing test assertions to set-based containment**

In `tests/unit/stages/physical/test_physical_builder_node.py` L84-91, replace:

```python
assert client.calls[0]["tool_names"] == [
    "inspect_graph",
    "read_support_file",
    "write_mutation_file",
    "execute_mutation_file",
    "validate_graph",
]
assert "write_checkpoint_file" not in client.calls[0]["tool_names"]
```

with:

```python
tool_names = set(client.calls[0]["tool_names"])
assert {"inspect_graph", "read_support_file", "write_mutation_file", "execute_mutation_file", "validate_graph", "list_support_files", "find_images", "get_image"}.issubset(tool_names)
assert "write_checkpoint_file" not in tool_names
```

In `tests/unit/stages/physical/test_physical_repair_node.py` L71-78, replace:

```python
assert client.calls[0]["tool_names"] == [
    "inspect_graph",
    "read_support_file",
    "write_checkpoint_file",
    "write_mutation_file",
    "execute_mutation_file",
    "validate_graph",
]
```

with:

```python
tool_names = set(client.calls[0]["tool_names"])
assert {"inspect_graph", "read_support_file", "write_checkpoint_file", "write_mutation_file", "execute_mutation_file", "validate_graph", "list_support_files", "find_images", "get_image"}.issubset(tool_names)
```

Add a new test in `tests/unit/stages/physical/test_physical_author_node.py`:

```python
def test_physical_author_tool_names_include_image_tools():
    state = _minimal_physical_author_state()  # use existing helper or inline
    from trace.stages.physical.nodes.author import PhysicalAuthorTools
    tools = PhysicalAuthorTools(state=state, physical_constraints=[]).as_agent_tools()
    names = {tool.name for tool in tools}
    assert "find_images" in names
    assert "get_image" in names
```

If `_minimal_physical_author_state` does not exist, inline:

```python
def _minimal_physical_author_state():
    return {"support_files": {"ground/physical_constraints.json": "{}"}}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/stages/physical -v`
Expected: FAIL — tool names don't yet include image tools.

- [ ] **Step 3: Wire image tools in PhysicalAuthorTools**

In `src/trace/stages/physical/nodes/author.py` extend `as_agent_tools`:

```python
from trace.stages.repair_tools import _FindImagesInput, _GetImageInput
from trace.tools.images.catalog import find_images, get_image

# inside as_agent_tools, after existing four tools:
@tool("find_images", args_schema=_FindImagesInput)
def find_images_tool(
    query: str | None = None,
    roles: list[str] | None = None,
    node_type: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Search the image catalog by free-text query, role list, or node type. Returns ranked candidate images with default_flavor."""
    return {"images": find_images(query=query, roles=roles, node_type=node_type, limit=limit)}


@tool("get_image", args_schema=_GetImageInput)
def get_image_tool(image_id: str) -> dict[str, Any]:
    """Look up a specific image_id in the catalog. Returns image, roles, node_types, aliases, default_flavor."""
    try:
        return get_image(image_id)
    except KeyError as exc:
        return {"ok": False, "error": {"message": str(exc)}}


return [
    write_checkpoint_file_tool,
    remove_checkpoint_file_tool,
    read_constraint_file_tool,
    validate_checkpoint_file_tool,
    find_images_tool,
    get_image_tool,
]
```

- [ ] **Step 4: Pass `include_image_tools=True` in physical builder and repair**

In `src/trace/stages/physical/nodes/builder.py`, change:

```python
tools=tools.as_agent_tools(include_checkpoint_tool=False),
```

to:

```python
tools=tools.as_agent_tools(include_checkpoint_tool=False, include_image_tools=True),
```

In `src/trace/stages/physical/nodes/repair.py`, same flag added to the `repair_tools.as_agent_tools()` call.

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/unit/stages/physical -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/trace/stages/physical tests/unit/stages/physical
git commit -m "feat(physical): wire find_images and get_image into author/builder/repair tool lists"
```

### Task 1.9: Remove `image_catalog` system injection (three physical sites) and update breaking tests

**Files:**
- Modify: `src/trace/stages/physical/nodes/author.py` (drop `image_catalog` key from `system_context_sections`; remove `image_catalog_prompt` import)
- Modify: `src/trace/stages/physical/nodes/builder.py` (same)
- Modify: `src/trace/stages/physical/nodes/repair.py` (drop the `image_catalog` system message in `_build_repair_messages`; remove the `image_catalog` parameter; remove `image_catalog_prompt` import)
- Update tests:
  - `tests/unit/stages/physical/test_physical_author_node.py` L42-43 — replace `[image_catalog]` / `img_pfsense` positive assertions with negative
  - `tests/unit/stages/physical/test_physical_builder_node.py` L93-94 — same
  - `tests/unit/stages/physical/test_physical_repair_node.py` L131-132 — replace `Image catalog for this repair round` positive with negative

- [ ] **Step 1: Flip the six positive assertions to negative**

In `tests/unit/stages/physical/test_physical_author_node.py` L42-43:

```python
assert "[image_catalog]" not in system_content
assert "img_pfsense" not in system_content
```

In `tests/unit/stages/physical/test_physical_builder_node.py` L93-94:

```python
assert "[image_catalog]" not in system_content
assert "img_pfsense" not in system_content
```

In `tests/unit/stages/physical/test_physical_repair_node.py` L131-132:

```python
assert "Image catalog for this repair round" not in messages[2]["content"] if len(messages) > 2 else True
assert all("img_pfsense" not in msg.get("content", "") for msg in messages)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/stages/physical -v`
Expected: FAIL on these three files because image_catalog is still injected.

- [ ] **Step 3: Drop `image_catalog` from author and builder**

`physical/nodes/author.py`:
- Remove `from trace.tools.images.catalog import image_catalog_prompt`.
- Remove the `"image_catalog": image_catalog_prompt(),` entry from `system_context_sections`.

`physical/nodes/builder.py`:
- Same two removals.

- [ ] **Step 4: Drop `image_catalog` from repair**

`physical/nodes/repair.py`:
- Remove `from trace.tools.images.catalog import image_catalog_prompt`.
- Remove the `image_catalog=image_catalog_prompt(),` argument from the `_build_repair_messages(...)` call.
- Update `_build_repair_messages` signature to drop `image_catalog: str` parameter.
- Remove the `{"role": "system", "content": "Image catalog for this repair round:\n\n" + image_catalog},` system message.

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/unit/stages -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/trace/stages/physical/nodes tests/unit/stages/physical
git commit -m "refactor(physical): drop image_catalog system injection in favor of tool-based access"
```

### Task 1.10: Fix `segment` semantics in playbooks and docs

**Files:**
- Modify: `src/tgraph/agent/playbooks/authoring.md` — ADD a new "TGraph Check / Editor API" subsection that explicitly describes `check_interface` and `ensure_interface` with `segment` required.
- Modify: `src/tgraph/agent/playbooks/capabilities.md` — at line 29 remove the `segment` token from the "unsupported IR fields" list.
- Modify: `src/tgraph/agent/playbooks/repair.md` — add line: "When choosing images, use `find_images` / `get_image` agent tools. Do not recall `image_id` from memory."
- Modify: `src/tgraph/agent/docs/tgraph_check_api.md` — update `check_interface` signature line and add a one-line parameter-vs-IR-field note.
- Modify: `src/tgraph/agent/docs/tgraph_editor_api.md` — same for `ensure_interface`.
- Create test: `tests/unit/tgraph/agent/test_playbook_segment.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/tgraph/agent/test_playbook_segment.py
from tgraph.agent.protocol import playbook_paths, doc_paths


def test_authoring_playbook_mentions_check_interface_and_marks_segment_required():
    text = playbook_paths()["authoring"].read_text(encoding="utf-8")
    assert "check_interface" in text
    assert "ensure_interface" in text
    para = next(p for p in text.split("\n\n") if "check_interface" in p or "ensure_interface" in p)
    assert "required" in para.lower() or "must" in para.lower()


def test_authoring_playbook_clarifies_segment_meaning():
    text = playbook_paths()["authoring"].read_text(encoding="utf-8")
    assert "neighboring" in text.lower() or "switch node id" in text.lower() or "not an IR field" in text.lower()


def test_capabilities_playbook_no_longer_lists_segment_as_unsupported_ir_field():
    text = playbook_paths()["capabilities"].read_text(encoding="utf-8")
    # The `unsupported IR fields` enumeration must not include `segment`.
    # We accept both bullet styles.
    forbidden_line_fragments = [
        "`software`, `packages`, `zone`, `segment`",
        "`software`, `packages`, `segment`",
        "`segment`, `firewall_rules`",
    ]
    for fragment in forbidden_line_fragments:
        assert fragment not in text


def test_repair_playbook_mentions_image_tools():
    text = playbook_paths()["repair"].read_text(encoding="utf-8")
    assert "find_images" in text
    assert "get_image" in text


def test_tgraph_check_api_doc_marks_segment_required():
    text = doc_paths()["readme"].parent.joinpath("tgraph_check_api.md").read_text(encoding="utf-8")
    assert "segment" in text
    assert "required" in text.lower() or "must" in text.lower() or "parameter" in text.lower()


def test_tgraph_editor_api_doc_marks_segment_required():
    text = doc_paths()["readme"].parent.joinpath("tgraph_editor_api.md").read_text(encoding="utf-8")
    assert "ensure_interface" in text
    assert "segment" in text
    assert "parameter" in text.lower() or "neighboring" in text.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/tgraph/agent/test_playbook_segment.py -v`
Expected: FAIL on all assertions.

- [ ] **Step 3: Update `playbooks/authoring.md` (ADD subsection)**

Append to `src/tgraph/agent/playbooks/authoring.md`:

```markdown

## TGraph Check / Editor API (interface fact authoring)

When the constraint is interface-shaped, use these APIs explicitly:

- `tgraph.check_interface(node, segment=..., cidr=None, ip=None, link_key=None)`
  - `segment` is **required**; it is the neighboring switch / segment-carrier node id (a function parameter that points to another node), not an IR field on nodes or ports.
  - `cidr`, `ip`, and `link_key` are optional refinements.
- `tgraph.ensure_interface(node, segment=..., cidr=..., ip=None, link_key=None)`
  - Same `segment` semantics. The mutation creates or updates the interface port.

`segment` always identifies an existing node id. It is never a top-level IR field.
```

- [ ] **Step 4: Update `playbooks/capabilities.md` (REMOVE segment token)**

In `src/tgraph/agent/playbooks/capabilities.md` line 29, change:

```
- represent unsupported IR fields such as `software`, `packages`, `zone`, `segment`, `firewall_rules`, or provider-specific deployment plans
```

to:

```
- represent unsupported IR fields such as `software`, `packages`, `zone`, `firewall_rules`, or provider-specific deployment plans (`segment` is a function parameter pointing to a neighboring node, not an IR field)
```

- [ ] **Step 5: Update `playbooks/repair.md` (ADD image-tools reminder)**

Append a short section to `src/tgraph/agent/playbooks/repair.md`:

```markdown

## Image Selection

When choosing images during physical-stage repair, use the `find_images` and `get_image` agent tools. Do not recall `image_id` from memory.
```

- [ ] **Step 6: Update docs**

In `src/tgraph/agent/docs/tgraph_check_api.md`, change the `check_interface` line to:

```
tgraph.check_interface(node, segment=..., cidr=None, ip=None, link_key=None)  # segment is required: neighboring node id (parameter, not an IR field)
```

In `src/tgraph/agent/docs/tgraph_editor_api.md`, change the `ensure_interface` line similarly and add at bottom: "`segment` is always a function parameter referring to another node id — never an IR field."

- [ ] **Step 7: Run tests to verify pass**

Run: `pytest tests/unit/tgraph/agent/test_playbook_segment.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/tgraph/agent tests/unit/tgraph/agent/test_playbook_segment.py
git commit -m "docs(tgraph): mark segment a required parameter, not an IR field; add image-tools reminder"
```

### Task 1.11: Strip TGraph API listings from six agent-role prompts and add final-message constraint

**Files:**
- Modify (agent-role prompts only — ground prompts excluded):
  - `src/trace/stages/logical/prompts/author.md`
  - `src/trace/stages/logical/prompts/builder.md`
  - `src/trace/stages/logical/prompts/repair.md`
  - `src/trace/stages/physical/prompts/author.md`
  - `src/trace/stages/physical/prompts/builder.md`
  - `src/trace/stages/physical/prompts/repair.md`
- Leave UNCHANGED:
  - `src/trace/stages/ground/prompts/author.md` (structured role; "Return only a JSON object" contract)
  - `src/trace/stages/ground/prompts/evaluator.md` (structured role)
- Create test: `tests/unit/stages/test_prompts_surface.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/stages/test_prompts_surface.py
from pathlib import Path

PROMPT_ROOT = Path(__file__).resolve().parents[3] / "src" / "trace" / "stages"
AGENT_PROMPT_ROOTS = [
    PROMPT_ROOT / "logical" / "prompts",
    PROMPT_ROOT / "physical" / "prompts",
]
STRUCTURED_PROMPT_ROOTS = [PROMPT_ROOT / "ground" / "prompts"]


def _agent_prompts() -> list[Path]:
    return [p for root in AGENT_PROMPT_ROOTS for p in root.glob("*.md")]


def _structured_prompts() -> list[Path]:
    return [p for root in STRUCTURED_PROMPT_ROOTS for p in root.glob("*.md")]


def test_no_tgraph_api_listings_in_agent_prompts():
    forbidden = (
        "tgraph.check_subnet",
        "tgraph.check_interface",
        "tgraph.check_direct_link",
        "tgraph.check_chain",
        "tgraph.check_ring",
        "tgraph.check_star",
        "tgraph.check_mesh",
        "tgraph.check_image_exact",
        "tgraph.check_flavor_minimum",
        "tgraph.check_flavor_exact",
        "tgraph.ensure_direct_link",
        "tgraph.ensure_chain",
        "tgraph.ensure_ring",
        "tgraph.ensure_star",
        "tgraph.ensure_mesh",
        "tgraph.ensure_subnet",
        "tgraph.ensure_interface",
        "tgraph.set_image",
        "tgraph.set_flavor",
    )
    for path in _agent_prompts():
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            # Allow physical/author.md to reference tgraph.check_* INSIDE the kind→tool decision table only
            if path.name == "author.md" and "Kind→Tool" in text and token in {"tgraph.check_image_exact", "tgraph.check_flavor_exact", "tgraph.check_flavor_minimum"}:
                continue
            assert token not in text, f"{path} still mentions {token}"


def test_agent_prompts_end_with_final_message_constraint():
    for path in _agent_prompts():
        text = path.read_text(encoding="utf-8")
        assert "Final message MUST be a one-sentence action summary" in text, f"{path.name} missing constraint"


def test_structured_prompts_do_not_carry_final_message_constraint():
    # Final-message constraint would contradict "Return only a JSON object" in ground prompts.
    for path in _structured_prompts():
        text = path.read_text(encoding="utf-8")
        assert "Final message MUST be a one-sentence action summary" not in text


def test_physical_author_prompt_has_kind_tool_decision_table():
    text = (PROMPT_ROOT / "physical" / "prompts" / "author.md").read_text(encoding="utf-8")
    assert "Kind" in text and "tgraph.check_image_exact" in text
    assert "physical.image.exact" in text
    assert "physical.image.capability" in text


def test_logical_builder_prompt_does_not_forbid_segment_keyword():
    text = (PROMPT_ROOT / "logical" / "prompts" / "builder.md").read_text(encoding="utf-8")
    assert "Do not invent unsupported IR fields such as `segment`" not in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/stages/test_prompts_surface.py -v`
Expected: FAIL on multiple assertions.

- [ ] **Step 3: Edit six agent prompts**

For each agent prompt:

a. Delete entire `## TGraph Check API`, `## TGraph Editor API`, `## Mutation Contract`, `## Available Tools` API-list-style blocks. Keep role guidance, tool-flow narrative, examples that reference tools but not API surface lists.

b. Specifically:

  - `logical/prompts/author.md` — delete `## TGraph Check API` section (8 `tgraph.check_*` lines) AND delete the `## Example` block at L47-52 (contains `tgraph.check_chain`). The custom-issue guidance code block at L26-45 may remain because it only uses `tgraph.path_exists`, `tgraph.issue` style helpers (no `tgraph.check_*` / `tgraph.ensure_*` / `tgraph.set_*` tokens — verify with grep after editing).
  - `logical/prompts/builder.md` — delete `## Mutation Contract` API list (the 7 `tgraph.ensure_*` lines), keep `def mutate(tgraph):` skeleton. Replace `"Do not invent unsupported IR fields such as 'segment', 'zone', 'firewall_rules', 'software', or 'packages'."` with: `"Do not invent unsupported IR fields such as 'zone', 'firewall_rules', 'software', or 'packages'. 'segment' is a parameter of ensure_interface pointing to a neighboring switch node id — pass an existing node id."`
  - `logical/prompts/repair.md` — delete `## Available Tools` enumeration AND delete the `## Mutation Example` block at L20-25 (contains `tgraph.ensure_chain` / `tgraph.ensure_subnet`).
  - `physical/prompts/author.md` — delete `## TGraph Check API`; the Kind→Tool table comes in Task 1.12.
  - `physical/prompts/builder.md` — delete `## Mutation Contract` API list; the switch hint comes in Task 1.13.
  - `physical/prompts/repair.md` — delete `## Available Tools` AND delete the `## Mutation Example` block at L21-26 (contains `tgraph.set_image` / `tgraph.set_flavor`); also rewrite L16 "Image and flavor choices must come from `image_catalog` or explicit static knowledge supplied in context." to "Image and flavor choices must come from `find_images` / `get_image` agent tools or explicit static knowledge supplied in context."

(All deleted code examples were API surface exposure; the spec mandates that API surface live exclusively in `tgraph_contract` / playbooks / docs.)

c. Append to each of the six agent prompts (last line, plain text):

```
Final message MUST be a one-sentence action summary; do not restate the artifact or repeat code.
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/stages/test_prompts_surface.py -v`
Expected: PASS on `test_no_tgraph_api_listings_in_agent_prompts`, `test_agent_prompts_end_with_final_message_constraint`, `test_structured_prompts_do_not_carry_final_message_constraint`, `test_logical_builder_prompt_does_not_forbid_segment_keyword`. The kind→tool decision table test still FAILS (will pass after Task 1.12).

- [ ] **Step 5: Commit**

```bash
git add src/trace/stages/logical/prompts src/trace/stages/physical/prompts tests/unit/stages/test_prompts_surface.py
git commit -m "refactor(prompts): strip TGraph API listings from agent prompts; add final-message constraint"
```

### Task 1.12: Add physical author Kind→Tool decision table

**Files:**
- Modify: `src/trace/stages/physical/prompts/author.md`
- The relevant test `test_physical_author_prompt_has_kind_tool_decision_table` is already in `tests/unit/stages/test_prompts_surface.py`.

- [ ] **Step 1: Verify the test is currently failing**

Run: `pytest tests/unit/stages/test_prompts_surface.py::test_physical_author_prompt_has_kind_tool_decision_table -v`
Expected: FAIL.

- [ ] **Step 2: Insert the decision table block**

Append to `src/trace/stages/physical/prompts/author.md` (before the final-message constraint added in Task 1.11):

```markdown

## Kind→Tool Decision Table

| constraint kind             | how to author check                                                                 |
|-----------------------------|--------------------------------------------------------------------------------------|
| physical.image.exact        | use `tgraph.check_image_exact(node, image_id)`                                       |
| physical.image.capability   | custom check; first call `find_images(roles=..., query=...)` to enumerate candidate `image_ids`, then encode `expected_image_ids` in issue details |
| physical.flavor.exact       | use `tgraph.check_flavor_exact(node, vcpu=..., ram=..., disk=...)`                   |
| physical.flavor.minimum     | use `tgraph.check_flavor_minimum(node, vcpu=..., ram=..., disk=...)`                 |
| physical.custom             | custom check; describe the rule in plain Python                                      |

Non-`custom` and non-`capability` kinds must go through the matching `tgraph.check_*` API. Do not wrap them in hand-written if-else.
```

(Note: this is the **only** allowed appearance of `tgraph.check_image_exact` / `tgraph.check_flavor_*` in any prompt — the surface test in Task 1.11 explicitly whitelists this file for those tokens.)

- [ ] **Step 3: Run test to verify pass**

Run: `pytest tests/unit/stages/test_prompts_surface.py -v`
Expected: PASS for all in this file.

- [ ] **Step 4: Commit**

```bash
git add src/trace/stages/physical/prompts/author.md
git commit -m "docs(physical_author): add kind-to-tool decision table"
```

### Task 1.13: Add physical builder switch-iteration hint

**Files:**
- Modify: `src/trace/stages/physical/prompts/builder.md`
- Modify: `tests/unit/stages/test_prompts_surface.py` (add one assertion)

- [ ] **Step 1: Write failing test**

Append to `tests/unit/stages/test_prompts_surface.py`:

```python
def test_physical_builder_prompt_hints_switch_iteration():
    text = (PROMPT_ROOT / "physical" / "prompts" / "builder.md").read_text(encoding="utf-8")
    assert "find_images(node_type='switch')" in text or 'find_images(node_type="switch")' in text
    assert "do not skip" in text.lower() or "every switch" in text.lower()
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/unit/stages/test_prompts_surface.py::test_physical_builder_prompt_hints_switch_iteration -v`
Expected: FAIL.

- [ ] **Step 3: Append hint to builder prompt**

Append to `src/trace/stages/physical/prompts/builder.md` (just before the final-message constraint added in Task 1.11):

```markdown

## Switch Coverage

Use `find_images(node_type='switch')` to retrieve the switch image and default_flavor, then iterate every switch node when authoring mutation calls. Do not skip any switch node.
```

(This snippet uses bare `set_image` / `set_flavor` only in commentary if needed; the strict forbidden tokens in Task 1.11 are `tgraph.set_image` / `tgraph.set_flavor` with the `tgraph.` prefix, so bare verbs are fine.)

- [ ] **Step 4: Run test to verify pass**

Run: `pytest tests/unit/stages/test_prompts_surface.py::test_physical_builder_prompt_hints_switch_iteration -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/trace/stages/physical/prompts/builder.md tests/unit/stages/test_prompts_surface.py
git commit -m "docs(physical_builder): hint find_images for full switch coverage"
```

### Task 1.14: Verify full test suite and demo smoke

- [ ] **Step 1: Full unit suite**

Run: `pytest -q`
Expected: all green.

- [ ] **Step 2: Demo smoke (LangSmith disabled to keep run fast/offline)**

PowerShell:

```powershell
$env:LANGSMITH_TRACING="false"
trace run tests/demo/demo.md --run-id pr1-smoke-001 --output-root runs
```

Expected:
- `runs/pr1-smoke-001/run.json` `status` is `completed`.
- `runs/pr1-smoke-001/logical/repair_history.json` first round does not list a `check_interface` segment error (the demo-007 regression).
- `runs/pr1-smoke-001/physical/mutations/build.py` covers all image/flavor targets in a single mutation file (no `attempt_1.py` follow-up needed for switch image coverage).
- LangSmith trace (if re-enabled) shows `find_images` and `get_image` tool calls inside physical agent runs.

- [ ] **Step 3: Branch / PR**

Push the chunk-1 branch and open a PR titled `feat: PR1 prompt and tool surface cleanup`. Reference the spec section list in the PR description.

PR1 chunk done.

---

## Chunk 2: PR2 — Ledger Product-Pointers And Mutation Incrementality

This chunk builds on PR1's `MutationSummary` and `_derive_op_counts`. After PR2 merges, the agent gets a deterministic ledger of what was produced in each repair round plus a diff inspect view for incremental mutations.

**Branch / commit cadence:** ~12 commits, one per task.

### Task 2.1: Add `mutation_index_seed`, snapshot landing, and `snapshot_path` in `MutationSummary`

**Files:**
- Modify: `src/trace/stages/repair_tools.py`
- Create test: `tests/unit/stages/test_mutation_snapshot.py`
- Create test: `tests/unit/stages/test_mutation_index_seed.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/stages/test_mutation_snapshot.py`:

```python
import json
from pathlib import Path
from trace.stages.repair_tools import StageRepairTools


def _seed_logical_graph_dict() -> dict:
    return {
        "stage": "logical",
        "nodes": [{"id": "SW_DMZ", "type": "switch", "label": "SW_DMZ", "ports": []}],
        "links": [],
    }


def test_execute_mutation_file_writes_snapshot(tmp_path):
    artifact = {"graph": _seed_logical_graph_dict(), "constraint_files": {}, "checkpoint_files": {}}
    tools = StageRepairTools(artifact, support_file_root=str(tmp_path))
    write = tools.write_mutation_file(
        content="def mutate(tgraph):\n    tgraph.ensure_subnet('SW_DMZ', cidr='10.10.10.0/24')\n",
        path="logical/mutations/attempt_1.py",
    )
    result = tools.execute_mutation_file(path=write["path"], validate=False)
    snapshot_path = result["summary"]["snapshot_path"]
    assert snapshot_path == "logical/mutations/snapshots/attempt_1.json"
    assert (Path(tmp_path) / snapshot_path).exists()
    snapshot = json.loads((Path(tmp_path) / snapshot_path).read_text(encoding="utf-8"))
    assert snapshot["stage"] == "logical"


def test_execute_mutation_file_failure_does_not_write_snapshot(tmp_path):
    artifact = {"graph": _seed_logical_graph_dict(), "constraint_files": {}, "checkpoint_files": {}}
    tools = StageRepairTools(artifact, support_file_root=str(tmp_path))
    write = tools.write_mutation_file(
        content="def mutate(tgraph):\n    raise RuntimeError('boom')\n",
        path="logical/mutations/attempt_1.py",
    )
    result = tools.execute_mutation_file(path=write["path"], validate=False)
    assert result["ok"] is False
    assert result["summary"]["snapshot_path"] is None
    assert not (Path(tmp_path) / "logical/mutations/snapshots/attempt_1.json").exists()
```

`tests/unit/stages/test_mutation_index_seed.py`:

```python
from trace.stages.repair_tools import StageRepairTools


def _seed():
    return {
        "stage": "logical",
        "nodes": [{"id": "A", "type": "computer", "label": "A", "ports": []}],
        "links": [],
    }


def test_default_mutation_index_seed_is_one(tmp_path):
    tools = StageRepairTools({"graph": _seed(), "constraint_files": {}, "checkpoint_files": {}}, support_file_root=str(tmp_path))
    result = tools.write_mutation_file(content="def mutate(tgraph):\n    pass\n")
    assert result["path"] == "logical/mutations/attempt_1.py"


def test_mutation_index_seed_advances_attempt_number(tmp_path):
    tools = StageRepairTools(
        {"graph": _seed(), "constraint_files": {}, "checkpoint_files": {}},
        support_file_root=str(tmp_path),
        mutation_index_seed=3,
    )
    result = tools.write_mutation_file(content="def mutate(tgraph):\n    pass\n")
    assert result["path"] == "logical/mutations/attempt_3.py"


def test_mutation_index_seed_zero_falls_back_to_one(tmp_path):
    tools = StageRepairTools(
        {"graph": _seed(), "constraint_files": {}, "checkpoint_files": {}},
        support_file_root=str(tmp_path),
        mutation_index_seed=0,
    )
    result = tools.write_mutation_file(content="def mutate(tgraph):\n    pass\n")
    assert result["path"] == "logical/mutations/attempt_1.py"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/stages/test_mutation_snapshot.py tests/unit/stages/test_mutation_index_seed.py -v`
Expected: FAIL — `mutation_index_seed` parameter doesn't exist; snapshot not landed; `summary.snapshot_path` absent.

- [ ] **Step 3: Extend `MutationSummary` schema**

In `src/trace/stages/repair_tools.py`, add field to `MutationSummary`:

```python
class MutationSummary(BaseModel):
    stage: str
    node_count: int
    link_count: int
    affected_node_ids: list[str]
    affected_link_ids: list[str]
    op_counts: dict[str, int]
    snapshot_path: str | None = None
```

Update `from_operations` to optionally accept `snapshot_path: str | None = None` and pass it through.

- [ ] **Step 4: Extend `StageRepairTools.__init__` with `mutation_index_seed`**

```python
def __init__(
    self,
    artifact: dict[str, Any],
    *,
    support_files: dict[str, str] | None = None,
    support_file_root: str | None = None,
    logical_reference_graph: TGraph | dict[str, Any] | None = None,
    mutation_index_seed: int = 1,
) -> None:
    # ... existing init ...
    self._mutation_index = max(1, mutation_index_seed)
```

- [ ] **Step 5: Land snapshot inside `execute_mutation_file` on success**

```python
def execute_mutation_file(self, *, path: str, validate: bool = True, include_graph: bool = False) -> dict[str, Any]:
    normalized = _safe_relative_path(path)
    if normalized not in self._support_files:
        return {"ok": False, "error": {"message": f"support file not found: {normalized}"}}
    mutation_path = self._materialize_support_file(normalized)
    result = execute_mutation_file(
        self._graph_model(),
        mutation_path=mutation_path,
        validate=validate,
        validation_context=self._validation_context(),
    )
    operations = list(result.operations or [])
    if result.ok and result.graph is not None:
        self._artifact["graph"] = result.graph.model_dump(mode="json")

    snapshot_path: str | None = None
    if result.ok and result.graph is not None:
        attempt_id = self._attempt_id_for_mutation_path(normalized)
        if attempt_id is not None:
            snapshot_path = f"{result.graph.stage}/mutations/snapshots/attempt_{attempt_id}.json"
            self._write_support_file(
                snapshot_path,
                json.dumps(result.graph.model_dump(mode="json"), indent=2, ensure_ascii=False),
            )

    graph_model = self._graph_model()
    summary = MutationSummary.from_operations(
        stage=graph_model.stage,
        node_count=len(graph_model.nodes),
        link_count=len(graph_model.links),
        operations=operations,
        snapshot_path=snapshot_path,
    )
    payload: dict[str, Any] = {
        "ok": result.ok,
        "operations": [dict(op) for op in operations],
        "summary": summary.model_dump(mode="json"),
    }
    if not result.ok:
        payload["issues"] = [issue.model_dump(mode="json") for issue in result.issues]
    if include_graph and result.graph is not None:
        payload["graph"] = result.graph.model_dump(mode="json")
    return payload
```

Add helper:

```python
def _attempt_id_for_mutation_path(self, path: str) -> int | None:
    # path shape: "<stage>/mutations/attempt_<N>.py"
    import re
    match = re.match(r"^[^/]+/mutations/attempt_(\d+)\.py$", path)
    if not match:
        return None
    return int(match.group(1))
```

Note: `json` is already imported at the top of `repair_tools.py` (used by `filtered_view` in Chunk 1's edits). If not, add `import json` near the existing `from pathlib import Path` line.

- [ ] **Step 6: Run tests to verify pass**

Run: `pytest tests/unit/stages/test_mutation_snapshot.py tests/unit/stages/test_mutation_index_seed.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/trace/stages/repair_tools.py tests/unit/stages/test_mutation_snapshot.py tests/unit/stages/test_mutation_index_seed.py
git commit -m "feat(repair_tools): land mutation snapshot and support mutation_index_seed"
```

### Task 2.2: Implement `diff(current, baseline)` pure routine

**Files:**
- Create: `src/tgraph/operations/inspect/diff.py`
- Modify: `src/tgraph/operations/inspect/__init__.py` (dispatch `view="diff"`)
- Create test: `tests/unit/tgraph/operations/test_inspect_diff.py`

- [ ] **Step 1: Inventory the existing inspect dispatcher**

Run: `rg -n "view ==" src/tgraph/operations/inspect` to discover the existing dispatch pattern. Read the resulting `__init__.py` to understand how to add a new view.

- [ ] **Step 2: Write failing tests**

```python
# tests/unit/tgraph/operations/test_inspect_diff.py
from tgraph import TGraph
from tgraph.operations.inspect.diff import diff


def _build(stage, nodes, links=None):
    return TGraph.model_validate({
        "stage": stage,
        "nodes": nodes,
        "links": links or [],
    })


def test_diff_reports_added_nodes():
    baseline = _build("logical", [{"id": "A", "type": "computer", "label": "A", "ports": []}])
    current = _build(
        "logical",
        [
            {"id": "A", "type": "computer", "label": "A", "ports": []},
            {"id": "B", "type": "switch", "label": "B", "ports": []},
        ],
    )
    result = diff(current, baseline)
    assert result["added_nodes"] == ["B"]
    assert result["removed_nodes"] == []
    assert result["changed_nodes"] == []
    assert result["unchanged_count"] == 1


def test_diff_reports_removed_nodes():
    baseline = _build(
        "logical",
        [
            {"id": "A", "type": "computer", "label": "A", "ports": []},
            {"id": "B", "type": "switch", "label": "B", "ports": []},
        ],
    )
    current = _build("logical", [{"id": "A", "type": "computer", "label": "A", "ports": []}])
    result = diff(current, baseline)
    assert result["removed_nodes"] == ["B"]
    assert result["unchanged_count"] == 1


def test_diff_reports_changed_fields():
    baseline = _build(
        "physical",
        [{"id": "FIREWALL", "type": "computer", "label": "FIREWALL", "ports": [], "image": None, "flavor": None}],
    )
    current = _build(
        "physical",
        [
            {
                "id": "FIREWALL",
                "type": "computer",
                "label": "FIREWALL",
                "ports": [],
                "image": {"id": "img_pfsense", "name": "pfsense"},
                "flavor": {"vcpu": 2, "ram": 2048, "disk": 10},
            }
        ],
    )
    result = diff(current, baseline)
    assert result["added_nodes"] == []
    assert result["removed_nodes"] == []
    assert result["changed_nodes"] == [{"id": "FIREWALL", "fields_changed": ["flavor", "image"]}]


def test_diff_ignores_field_order_in_ports():
    baseline = _build(
        "logical",
        [{"id": "A", "type": "computer", "label": "A", "ports": [{"id": "_B-1"}]}],
    )
    current = _build(
        "logical",
        [{"id": "A", "type": "computer", "label": "A", "ports": [{"id": "_B-1"}]}],
    )
    result = diff(current, baseline)
    assert result["unchanged_count"] == 1
    assert result["changed_nodes"] == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/tgraph/operations/test_inspect_diff.py -v`
Expected: FAIL — `tgraph.operations.inspect.diff` module not found.

- [ ] **Step 4: Implement `diff.py`**

```python
# src/tgraph/operations/inspect/diff.py
from __future__ import annotations

from typing import Any

from tgraph.core.graph import TGraph

_NODE_FIELDS = ("type", "label", "image", "flavor", "ports", "metadata")


def diff(current: TGraph, baseline: TGraph) -> dict[str, Any]:
    current_nodes = {node.id: node for node in current.nodes}
    baseline_nodes = {node.id: node for node in baseline.nodes}

    added = sorted(current_nodes.keys() - baseline_nodes.keys())
    removed = sorted(baseline_nodes.keys() - current_nodes.keys())

    changed: list[dict[str, Any]] = []
    unchanged = 0
    for node_id in sorted(current_nodes.keys() & baseline_nodes.keys()):
        cur = current_nodes[node_id].model_dump(mode="json")
        base = baseline_nodes[node_id].model_dump(mode="json")
        diff_fields = sorted({field for field in _NODE_FIELDS if cur.get(field) != base.get(field)})
        if diff_fields:
            changed.append({"id": node_id, "fields_changed": diff_fields})
        else:
            unchanged += 1

    return {
        "added_nodes": added,
        "removed_nodes": removed,
        "changed_nodes": changed,
        "unchanged_count": unchanged,
    }
```

- [ ] **Step 5: Register `view="diff"` dispatcher in `src/tgraph/operations/inspect/__init__.py`**

Add to the existing dispatcher (the file already routes `view` strings to handlers):

```python
from tgraph.operations.inspect.diff import diff as _diff_view


def inspect_graph(graph: TGraph, *, view: str = "summary", **kwargs: Any) -> dict[str, Any]:
    # ... existing branches ...
    if view == "diff":
        baseline = kwargs.get("baseline")
        if baseline is None:
            raise ValueError("inspect_graph(view='diff') requires a baseline TGraph")
        return _diff_view(graph, baseline)
    # ... default ...
```

If the existing `__init__.py` uses a dispatch table rather than if/elif chain, register `"diff": _diff_view_with_baseline_unpack` accordingly. Read the existing dispatcher first; mirror its style.

- [ ] **Step 6: Run tests to verify pass**

Run: `pytest tests/unit/tgraph/operations/test_inspect_diff.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/tgraph/operations/inspect/diff.py src/tgraph/operations/inspect/__init__.py tests/unit/tgraph/operations/test_inspect_diff.py
git commit -m "feat(tgraph_inspect): add diff view for incremental change detection"
```

### Task 2.3: Wire `inspect_graph(view="diff", against=...)` into `StageRepairTools`

**Files:**
- Modify: `src/trace/stages/repair_tools.py` (`_InspectGraphToolInput` adds `against`; `inspect_graph` method dispatches; tool docstring)
- Create test: `tests/unit/stages/test_inspect_graph_diff.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/stages/test_inspect_graph_diff.py
import json
from pathlib import Path
from trace.stages.repair_tools import StageRepairTools


def _physical(nodes=None, links=None):
    return {
        "stage": "physical",
        "nodes": nodes or [],
        "links": links or [],
    }


def _logical(nodes=None, links=None):
    return {
        "stage": "logical",
        "nodes": nodes or [],
        "links": links or [],
    }


def test_inspect_graph_diff_against_logical_reference():
    logical_ref = _logical([{"id": "FIREWALL", "type": "computer", "label": "FIREWALL", "ports": []}])
    physical_artifact = {
        "graph": _physical(
            [
                {
                    "id": "FIREWALL",
                    "type": "computer",
                    "label": "FIREWALL",
                    "ports": [],
                    "image": {"id": "img_pfsense", "name": "pfsense"},
                    "flavor": {"vcpu": 2, "ram": 2048, "disk": 10},
                }
            ]
        ),
        "constraint_files": {},
        "checkpoint_files": {},
    }
    tools = StageRepairTools(physical_artifact, logical_reference_graph=logical_ref)
    result = tools.inspect_graph(view="diff", against="logical_reference")
    assert result["changed_nodes"] == [{"id": "FIREWALL", "fields_changed": ["flavor", "image"]}]


def test_inspect_graph_diff_against_previous_attempt_uses_snapshot(tmp_path):
    artifact = {"graph": _logical([{"id": "A", "type": "computer", "label": "A", "ports": []}]), "constraint_files": {}, "checkpoint_files": {}}
    tools = StageRepairTools(artifact, support_file_root=str(tmp_path))
    write = tools.write_mutation_file(
        content="def mutate(tgraph):\n    tgraph.ensure_node('B', type='switch', label='B')\n",
        path="logical/mutations/attempt_1.py",
    )
    tools.execute_mutation_file(path=write["path"], validate=False)
    # Now graph has A + B; baseline snapshot has A + B too (post-mutation snapshot).
    # Append another mutation to add C.
    write2 = tools.write_mutation_file(
        content="def mutate(tgraph):\n    tgraph.ensure_node('C', type='computer', label='C')\n",
        path="logical/mutations/attempt_2.py",
    )
    tools.execute_mutation_file(path=write2["path"], validate=False)
    # The previous_attempt baseline is attempt_2's snapshot which equals the current state,
    # so diff should be empty. Set baseline to attempt_1's snapshot manually to verify diff.
    result = tools.inspect_graph(view="diff", against="previous_attempt", baseline_attempt_id=1)
    # Against attempt_1 snapshot (A + B), current state (A + B + C) shows C as added.
    assert "C" in result["added_nodes"]


def test_inspect_graph_diff_previous_attempt_requires_existing_snapshot(tmp_path):
    artifact = {"graph": _logical([{"id": "A", "type": "computer", "label": "A", "ports": []}]), "constraint_files": {}, "checkpoint_files": {}}
    tools = StageRepairTools(artifact, support_file_root=str(tmp_path))
    result = tools.inspect_graph(view="diff", against="previous_attempt")
    assert result.get("ok") is False
    assert "no previous attempt snapshot" in result.get("error", {}).get("message", "").lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/stages/test_inspect_graph_diff.py -v`
Expected: FAIL — `against` parameter does not exist on inspect_graph yet.

- [ ] **Step 3: Extend `_InspectGraphToolInput` and `inspect_graph` method**

```python
class _InspectGraphToolInput(BaseModel):
    view: str = "summary"
    node_id: str | None = None
    port_id: str | None = None
    source: str | None = None
    target: str | None = None
    against: str | None = None
    baseline_attempt_id: int | None = None


def inspect_graph(
    self,
    *,
    view: str = "summary",
    against: str | None = None,
    baseline_attempt_id: int | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    if view == "diff":
        baseline_graph = self._resolve_diff_baseline(against=against, baseline_attempt_id=baseline_attempt_id)
        if isinstance(baseline_graph, dict) and baseline_graph.get("ok") is False:
            return baseline_graph
        return inspect_graph(self._graph_model(), view="diff", baseline=baseline_graph)
    return inspect_graph(self._graph_model(), view=view, **kwargs)


def _resolve_diff_baseline(
    self,
    *,
    against: str | None,
    baseline_attempt_id: int | None,
) -> Any:
    if against == "logical_reference":
        if self._logical_reference_graph is None:
            return {"ok": False, "error": {"message": "logical_reference graph not provided"}}
        return self._logical_reference_graph
    if against in ("previous_attempt", None):
        stage = self._graph_model().stage
        snapshot_prefix = f"{stage}/mutations/snapshots/attempt_"
        if baseline_attempt_id is not None:
            path = f"{snapshot_prefix}{baseline_attempt_id}.json"
            if path not in self._support_files:
                return {"ok": False, "error": {"message": f"snapshot not found: {path}"}}
            return TGraph.model_validate(json.loads(self._support_files[path]))
        candidates = sorted(
            (key for key in self._support_files if key.startswith(snapshot_prefix) and key.endswith(".json")),
            key=lambda k: int(k.rsplit("_", 1)[-1].split(".")[0]),
        )
        if not candidates:
            return {"ok": False, "error": {"message": "no previous attempt snapshot available"}}
        return TGraph.model_validate(json.loads(self._support_files[candidates[-1]]))
    return {"ok": False, "error": {"message": f"unknown against: {against!r}"}}
```

(Note: the existing import alias `from tgraph import ... inspect_graph` is shadowed inside the method by the call to the module-level `inspect_graph`. Rename the local import to `from tgraph import inspect_graph as _inspect_graph_view` at the top of the file and use `_inspect_graph_view(...)` inside the method to avoid name collision with the method.)

- [ ] **Step 4: Update tool wrapper to forward new params**

```python
@tool("inspect_graph", args_schema=_InspectGraphToolInput)
def inspect_graph_tool(
    view: str = "summary",
    node_id: str | None = None,
    port_id: str | None = None,
    source: str | None = None,
    target: str | None = None,
    against: str | None = None,
    baseline_attempt_id: int | None = None,
) -> dict[str, Any]:
    """Inspect the current graph. Views: summary, node, links, path, cidrs, diff. For view='diff' pass against='previous_attempt' or 'logical_reference' (and optionally baseline_attempt_id for previous_attempt)."""
    kwargs = {"node_id": node_id, "port_id": port_id, "source": source, "target": target}
    kwargs = {key: value for key, value in kwargs.items() if value is not None}
    return self.inspect_graph(view=view, against=against, baseline_attempt_id=baseline_attempt_id, **kwargs)
```

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/unit/stages/test_inspect_graph_diff.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/trace/stages/repair_tools.py tests/unit/stages/test_inspect_graph_diff.py
git commit -m "feat(repair_tools): wire inspect_graph diff view into stage tools"
```

### Task 2.4: Implement `_derive_produced_files` helper (path-precise pairing)

**Files:**
- Modify: `src/trace/stages/repair_tools.py` (add the helper at module level, shared between logical and physical repair modules)
- Create test: `tests/unit/stages/test_produced_files.py`

- [ ] **Step 1: Write failing tests covering NI-2 path-precise pairing**

```python
# tests/unit/stages/test_produced_files.py
from trace.stages.repair_tools import _derive_produced_files


def _attempt(tool_name, args, ok=True, result=None):
    entry = {"tool": tool_name, "args": args, "ok": ok}
    if result is not None:
        entry["result"] = result
    return entry


def test_mutation_paired_with_execute_by_exact_path():
    attempts = [
        _attempt("write_mutation_file", {"path": "logical/mutations/attempt_1.py", "content": "def mutate(tgraph): pass\n"}),
        _attempt("execute_mutation_file", {"path": "logical/mutations/attempt_1.py"}, ok=True, result={
            "ok": True,
            "operations": [{"op": "set_image", "node": "A"}, {"op": "set_image", "node": "B"}],
            "summary": {
                "op_counts": {"set_image": 2},
                "affected_node_ids": ["A", "B"],
                "snapshot_path": "logical/mutations/snapshots/attempt_1.json",
            },
        }),
    ]
    produced = _derive_produced_files(attempts)
    assert len(produced) == 1
    assert produced[0]["path"] == "logical/mutations/attempt_1.py"
    assert produced[0]["file_kind"] == "mutation"
    assert produced[0]["node_targets"] == ["A", "B"]
    assert produced[0]["op_counts"] == {"set_image": 2}
    assert produced[0]["snapshot_path"] == "logical/mutations/snapshots/attempt_1.json"
    assert "set_image x2 on [A, B]" in produced[0]["summary_one_line"]


def test_pairing_uses_exact_path_match_not_adjacency():
    # NI-2: out-of-order: write A, write B, execute B, execute A.
    attempts = [
        _attempt("write_mutation_file", {"path": "logical/mutations/attempt_1.py", "content": "x"}),
        _attempt("write_mutation_file", {"path": "logical/mutations/attempt_2.py", "content": "y"}),
        _attempt("execute_mutation_file", {"path": "logical/mutations/attempt_2.py"}, ok=True, result={
            "ok": True,
            "operations": [{"op": "ensure_subnet", "node": "SW"}],
            "summary": {"op_counts": {"ensure_subnet": 1}, "affected_node_ids": ["SW"], "snapshot_path": "logical/mutations/snapshots/attempt_2.json"},
        }),
        _attempt("execute_mutation_file", {"path": "logical/mutations/attempt_1.py"}, ok=True, result={
            "ok": True,
            "operations": [{"op": "ensure_node", "node": "A"}],
            "summary": {"op_counts": {"ensure_node": 1}, "affected_node_ids": ["A"], "snapshot_path": "logical/mutations/snapshots/attempt_1.json"},
        }),
    ]
    produced = _derive_produced_files(attempts)
    by_path = {p["path"]: p for p in produced}
    assert by_path["logical/mutations/attempt_1.py"]["node_targets"] == ["A"]
    assert by_path["logical/mutations/attempt_2.py"]["node_targets"] == ["SW"]


def test_mutation_written_but_not_executed_has_empty_op_counts():
    attempts = [
        _attempt("write_mutation_file", {"path": "logical/mutations/attempt_1.py", "content": "x"}),
    ]
    produced = _derive_produced_files(attempts)
    assert produced[0]["op_counts"] == {}
    assert produced[0]["node_targets"] == []
    assert produced[0]["snapshot_path"] is None


def test_checkpoint_file_derived_with_function_summary():
    attempts = [
        _attempt(
            "write_checkpoint_file",
            {
                "path": "logical/checkpoints.py",
                "content": "def check_lc1(tgraph):\n    return []\n\ndef check_lc17(tgraph):\n    return []\n",
            },
        ),
    ]
    produced = _derive_produced_files(attempts)
    assert len(produced) == 1
    assert produced[0]["file_kind"] == "checkpoint"
    assert produced[0]["node_targets"] == []
    assert "checkpoint defines: check_lc1, check_lc17" in produced[0]["summary_one_line"]


def test_pairing_picks_latest_successful_execute_for_same_path():
    # If a path was executed twice, take the latest successful execute.
    attempts = [
        _attempt("write_mutation_file", {"path": "logical/mutations/attempt_1.py", "content": "x"}),
        _attempt("execute_mutation_file", {"path": "logical/mutations/attempt_1.py"}, ok=False, result={
            "ok": False,
            "operations": [],
            "summary": {"op_counts": {}, "affected_node_ids": [], "snapshot_path": None},
        }),
        _attempt("execute_mutation_file", {"path": "logical/mutations/attempt_1.py"}, ok=True, result={
            "ok": True,
            "operations": [{"op": "ensure_node", "node": "A"}],
            "summary": {"op_counts": {"ensure_node": 1}, "affected_node_ids": ["A"], "snapshot_path": "logical/mutations/snapshots/attempt_1.json"},
        }),
    ]
    produced = _derive_produced_files(attempts)
    assert produced[0]["node_targets"] == ["A"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/stages/test_produced_files.py -v`
Expected: FAIL — `_derive_produced_files` doesn't exist yet.

- [ ] **Step 3: Implement `_derive_produced_files`**

Add to `src/trace/stages/repair_tools.py` (module level):

```python
import re
from typing import Iterable


_CHECK_FN_PATTERN = re.compile(r"^\s*def\s+(check_[A-Za-z0-9_]+)\s*\(", re.MULTILINE)


def _derive_produced_files(attempted_actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Index latest successful execute by exact mutation path.
    latest_exec_by_path: dict[str, dict[str, Any]] = {}
    for action in attempted_actions:
        if action.get("tool") != "execute_mutation_file":
            continue
        path = (action.get("args") or {}).get("path")
        if not isinstance(path, str):
            continue
        if action.get("ok") is True:
            latest_exec_by_path[path] = action

    produced: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    for action in attempted_actions:
        tool_name = action.get("tool")
        args = action.get("args") or {}

        if tool_name == "write_mutation_file":
            path = args.get("path")
            if not isinstance(path, str) or path in seen_paths:
                continue
            seen_paths.add(path)
            paired_execute = latest_exec_by_path.get(path)
            summary_dict = ((paired_execute or {}).get("result") or {}).get("summary") or {}
            op_counts = summary_dict.get("op_counts") or {}
            node_targets = list(summary_dict.get("affected_node_ids") or [])
            snapshot_path = summary_dict.get("snapshot_path")
            produced.append(
                {
                    "path": path,
                    "file_kind": "mutation",
                    "node_targets": node_targets,
                    "op_counts": op_counts,
                    "summary_one_line": _summary_one_line_for_mutation(op_counts, node_targets),
                    "snapshot_path": snapshot_path,
                }
            )

        elif tool_name == "write_checkpoint_file":
            path = args.get("path")
            if not isinstance(path, str) or path in seen_paths:
                continue
            seen_paths.add(path)
            content = args.get("content") or ""
            fn_names = _CHECK_FN_PATTERN.findall(content)
            produced.append(
                {
                    "path": path,
                    "file_kind": "checkpoint",
                    "node_targets": [],
                    "op_counts": {},
                    "summary_one_line": _summary_one_line_for_checkpoint(fn_names),
                    "snapshot_path": None,
                }
            )

    return produced


def _summary_one_line_for_mutation(op_counts: dict[str, int], node_targets: list[str]) -> str:
    if not op_counts:
        return "mutation written; not yet executed"
    op_part = ", ".join(f"{op} x{count}" for op, count in sorted(op_counts.items()))
    if not node_targets:
        return op_part
    display = node_targets[:5]
    tail = f", ... +{len(node_targets) - 5} more" if len(node_targets) > 5 else ""
    return f"{op_part} on [{', '.join(display)}{tail}]"


def _summary_one_line_for_checkpoint(fn_names: list[str]) -> str:
    if not fn_names:
        return "checkpoint defines: <unknown>"
    display = fn_names[:5]
    tail = f", ... +{len(fn_names) - 5} more" if len(fn_names) > 5 else ""
    return f"checkpoint defines: {', '.join(display)}{tail}"
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/stages/test_produced_files.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/trace/stages/repair_tools.py tests/unit/stages/test_produced_files.py
git commit -m "feat(repair_tools): derive produced_files from tool attempts with path-precise pairing"
```

### Task 2.5: Extend `_build_repair_ledger_entry` and prompt section in logical/physical repair

**Files:**
- Modify: `src/trace/stages/logical/nodes/repair.py` (`_build_repair_ledger_entry` accepts `produced_files`; `_summarize_recent_repair_ledger` exposes them; `repair_node` derives via `_derive_produced_files`)
- Modify: `src/trace/stages/physical/nodes/repair.py` (same shape)
- Create test: `tests/unit/stages/test_recent_repair_ledger.py`
- Modify test: `tests/unit/stages/logical/test_repair_node.py` (assert `produced_files` populated)
- Modify test: `tests/unit/stages/physical/test_physical_repair_node.py` (same)

- [ ] **Step 1: Write failing tests for the ledger entry shape**

`tests/unit/stages/test_recent_repair_ledger.py`:

```python
from trace.stages.logical.nodes.repair import _build_repair_ledger_entry, _summarize_recent_repair_ledger


def test_ledger_entry_includes_produced_files():
    attempted = [
        {
            "tool": "write_mutation_file",
            "args": {"path": "logical/mutations/attempt_1.py", "content": "def mutate(t): pass\n"},
            "ok": True,
        },
        {
            "tool": "execute_mutation_file",
            "args": {"path": "logical/mutations/attempt_1.py"},
            "ok": True,
            "result": {
                "ok": True,
                "operations": [{"op": "ensure_node", "node": "A"}],
                "summary": {
                    "op_counts": {"ensure_node": 1},
                    "affected_node_ids": ["A"],
                    "snapshot_path": "logical/mutations/snapshots/attempt_1.json",
                },
            },
        },
    ]
    entry = _build_repair_ledger_entry(
        round_index=1,
        issues_before={"issues": [{"details": {"issue_kind": "missing_link"}}]},
        issues_after={"issues": []},
        attempted_actions=attempted,
    )
    assert entry["produced_files"] == [
        {
            "path": "logical/mutations/attempt_1.py",
            "file_kind": "mutation",
            "node_targets": ["A"],
            "op_counts": {"ensure_node": 1},
            "summary_one_line": "ensure_node x1 on [A]",
            "snapshot_path": "logical/mutations/snapshots/attempt_1.json",
        }
    ]


def test_recent_repair_ledger_summary_includes_produced_files():
    prior = [
        {
            "round": 1,
            "issue_kinds_before": ["missing_link"],
            "resolved_issue_kinds": ["missing_link"],
            "remaining_issue_kinds": [],
            "new_issue_kinds": [],
            "attempted_actions": [],
            "failed_actions": [],
            "produced_files": [
                {"path": "logical/mutations/attempt_1.py", "file_kind": "mutation", "node_targets": ["A"], "op_counts": {"ensure_node": 1}, "summary_one_line": "ensure_node x1 on [A]", "snapshot_path": "logical/mutations/snapshots/attempt_1.json"}
            ],
        }
    ]
    summary = _summarize_recent_repair_ledger(prior)
    assert summary[0]["produced_files"][0]["path"] == "logical/mutations/attempt_1.py"
```

In `tests/unit/stages/logical/test_repair_node.py` add at the end of `test_logical_repair_node_uses_mutation_file_tools_and_writes_back_artifact` (rename if needed):

```python
assert result["repair_history"][-1]["produced_files"][0]["file_kind"] == "mutation"
assert result["repair_history"][-1]["produced_files"][0]["path"] == "logical/mutations/attempt_1.py"
```

In `tests/unit/stages/physical/test_physical_repair_node.py::test_physical_repair_node_uses_mutation_file_tools_and_writes_back_artifact`:

```python
assert result["repair_history"][-1]["produced_files"][0]["file_kind"] == "mutation"
assert result["repair_history"][-1]["produced_files"][0]["path"] == "physical/mutations/attempt_1.py"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/stages/test_recent_repair_ledger.py tests/unit/stages/logical/test_repair_node.py tests/unit/stages/physical/test_physical_repair_node.py -v`
Expected: FAIL — `produced_files` field not produced yet.

- [ ] **Step 3: Modify `_build_repair_ledger_entry` in `src/trace/stages/logical/nodes/repair.py`**

```python
from trace.stages.repair_tools import _derive_produced_files


def _build_repair_ledger_entry(
    *,
    round_index: int,
    issues_before: dict[str, Any],
    issues_after: dict[str, Any],
    attempted_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    before = _issue_kinds(issues_before)
    after = _issue_kinds(issues_after)
    before_set = set(before)
    after_set = set(after)
    failed_actions = [item for item in attempted_actions if item.get("ok") is False]
    return {
        "round": round_index,
        "mode": "agent",
        "issue_count": len(issues_before.get("issues", [])),
        "issue_kinds_before": before,
        "resolved_issue_kinds": sorted(before_set - after_set),
        "remaining_issue_kinds": after,
        "new_issue_kinds": sorted(after_set - before_set),
        "attempted_actions": attempted_actions,
        "failed_actions": failed_actions,
        "produced_files": _derive_produced_files(attempted_actions),
    }
```

And update `_summarize_recent_repair_ledger` to include `produced_files`:

```python
def _summarize_recent_repair_ledger(repair_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for item in repair_history[-LEDGER_WINDOW:]:
        summary.append(
            {
                "round": item.get("round"),
                "issue_kinds_before": item.get("issue_kinds_before", []),
                "resolved_issue_kinds": item.get("resolved_issue_kinds", []),
                "remaining_issue_kinds": item.get("remaining_issue_kinds", []),
                "new_issue_kinds": item.get("new_issue_kinds", []),
                "attempted_actions": item.get("attempted_actions", []),
                "failed_actions": item.get("failed_actions", []),
                "produced_files": item.get("produced_files", []),
            }
        )
    return summary
```

- [ ] **Step 4: Apply identical changes to `src/trace/stages/physical/nodes/repair.py`**

Same imports, same helpers, same ledger entry shape. (Avoid copy-paste drift: if both modules grow further in PR3, extract a shared helper module; for PR2 keep them parallel.)

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/unit/stages/test_recent_repair_ledger.py tests/unit/stages/logical tests/unit/stages/physical -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/trace/stages/logical/nodes/repair.py src/trace/stages/physical/nodes/repair.py tests/unit/stages/test_recent_repair_ledger.py tests/unit/stages/logical/test_repair_node.py tests/unit/stages/physical/test_physical_repair_node.py
git commit -m "feat(repair): record produced_files in repair_history ledger"
```

### Task 2.6: Wire `mutation_index_seed` into all builder/repair callsites

**Files:**
- Modify: `src/trace/stages/logical/nodes/builder.py` (already uses no mutation_index — pass `mutation_index_seed=1` explicitly for symmetry)
- Modify: `src/trace/stages/physical/nodes/builder.py` (same)
- Modify: `src/trace/stages/logical/nodes/repair.py` (compute seed from repair_history length)
- Modify: `src/trace/stages/physical/nodes/repair.py` (same)
- Modify test: `tests/unit/stages/test_mutation_index_seed.py` (add integration tests asserting seed across node reentry)

- [ ] **Step 1: Write failing integration test for repair node reentry**

Append to `tests/unit/stages/test_mutation_index_seed.py`:

```python
def test_repair_node_passes_seeded_index(monkeypatch):
    captured = {}

    real_cls = __import__("trace.stages.repair_tools", fromlist=["StageRepairTools"]).StageRepairTools

    class SpyStageRepairTools(real_cls):
        def __init__(self, *args, mutation_index_seed: int = 1, **kwargs):
            captured["mutation_index_seed"] = mutation_index_seed
            super().__init__(*args, mutation_index_seed=mutation_index_seed, **kwargs)

    monkeypatch.setattr("trace.stages.logical.nodes.repair.StageRepairTools", SpyStageRepairTools)

    from trace.stages.logical.nodes.repair import repair_node

    state = {
        "draft_artifact": {
            "graph": {"stage": "logical", "nodes": [{"id": "A", "type": "computer", "label": "A", "ports": []}], "links": []},
            "constraint_files": {},
            "checkpoint_files": {},
        },
        "support_files": {},
        "evaluation_report": {"ok": False, "issues": []},
        "attempt": 0,
        "repair_history": [{}, {}],  # 2 prior rounds → expected seed = 3
        "events": [],
    }

    class FakeClient:
        def invoke_agent(self, **_):
            return {"messages": []}

    repair_node(state, FakeClient())
    assert captured["mutation_index_seed"] == 3
```

- [ ] **Step 2: Run test to verify fail**

Run: `pytest tests/unit/stages/test_mutation_index_seed.py::test_repair_node_passes_seeded_index -v`
Expected: FAIL.

- [ ] **Step 3: Pass seeded index in both repair nodes**

In `src/trace/stages/logical/nodes/repair.py`:

```python
repair_tools = StageRepairTools(
    state["draft_artifact"],
    support_files=state.get("support_files", {}),
    support_file_root=state.get("support_file_root"),
    mutation_index_seed=len(state.get("repair_history", [])) + 1,
)
```

Same in `src/trace/stages/physical/nodes/repair.py`.

- [ ] **Step 4: Pass `mutation_index_seed=1` explicitly in both builders (documentation parity)**

In `src/trace/stages/logical/nodes/builder.py` and `physical/nodes/builder.py`, where `StageRepairTools(...)` is constructed, add the keyword. Either of these patterns is acceptable:

```python
tools = StageRepairTools(
    artifact,
    support_files=state.get("support_files", {}),
    support_file_root=state.get("support_file_root"),
    mutation_index_seed=1,
)
```

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/unit/stages -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/trace/stages/logical/nodes src/trace/stages/physical/nodes tests/unit/stages/test_mutation_index_seed.py
git commit -m "feat(stages): seed StageRepairTools mutation index across node re-entries"
```

### Task 2.7: Update builder prompts for incremental mutations and inventory awareness

**Files:**
- Modify: `src/trace/stages/logical/prompts/builder.md`
- Modify: `src/trace/stages/physical/prompts/builder.md`
- Modify: `tests/unit/stages/test_prompts_surface.py` (assertions)

- [ ] **Step 1: Write failing prompt-content tests**

Append to `tests/unit/stages/test_prompts_surface.py`:

```python
def test_logical_builder_prompt_uses_incremental_guidance():
    text = (PROMPT_ROOT / "logical" / "prompts" / "builder.md").read_text(encoding="utf-8")
    assert "First inspect current graph" in text or "inspect the current graph" in text.lower()
    assert "incremental" in text.lower() or "only the ensure" in text.lower()


def test_physical_builder_prompt_uses_incremental_guidance():
    text = (PROMPT_ROOT / "physical" / "prompts" / "builder.md").read_text(encoding="utf-8")
    assert "First inspect current graph" in text or "inspect the current graph" in text.lower()
    assert "prepare" in text.lower() and "inventory" in text.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/stages/test_prompts_surface.py -k "incremental_guidance or inventory" -v`
Expected: FAIL.

- [ ] **Step 3: Replace mutation guidance in `logical/prompts/builder.md`**

Find the line that previously said something like "Write one complete mutation file, normally `logical/mutations/build.py`". Replace with:

```markdown

## Mutation Strategy

First inspect the current graph state. Then write only the `ensure_*` / `set_*` calls that change something — skip operations whose target state already matches. The `TGraphEditor` operations are idempotent, but writing redundant calls wastes context.

If this is not the first attempt within this stage run, call `inspect_graph(view="diff", against="previous_attempt")` before authoring to see what changed since the last successful mutation.
```

- [ ] **Step 4: Replace mutation guidance in `physical/prompts/builder.md`**

Append (or replace, depending on existing content):

```markdown

## Mutation Strategy

First inspect the current graph state. Then write only the `ensure_*` / `set_*` calls that change something — skip operations whose target state already matches.

Stay aligned with the prepare-seeded node inventory: every physical node was already created during the prepare phase. Your job is to set `image` and `flavor` on those nodes; do not invent new nodes or rewrite the inventory.

If this is not the first attempt within this stage run, call `inspect_graph(view="diff", against="previous_attempt")` before authoring.
```

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/unit/stages/test_prompts_surface.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/trace/stages/logical/prompts/builder.md src/trace/stages/physical/prompts/builder.md tests/unit/stages/test_prompts_surface.py
git commit -m "docs(builder): switch to incremental mutation guidance with diff inspection"
```

### Task 2.8: Update repair prompts for diff-inspection-driven incrementality

**Files:**
- Modify: `src/trace/stages/logical/prompts/repair.md`
- Modify: `src/trace/stages/physical/prompts/repair.md`
- Modify: `tests/unit/stages/test_prompts_surface.py` (assertions)

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/stages/test_prompts_surface.py`:

```python
def test_logical_repair_prompt_mentions_diff_against_previous_attempt():
    text = (PROMPT_ROOT / "logical" / "prompts" / "repair.md").read_text(encoding="utf-8")
    assert "against=" in text or "previous_attempt" in text


def test_physical_repair_prompt_mentions_diff_against_previous_attempt():
    text = (PROMPT_ROOT / "physical" / "prompts" / "repair.md").read_text(encoding="utf-8")
    assert "against=" in text or "previous_attempt" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/stages/test_prompts_surface.py -k "diff_against" -v`
Expected: FAIL.

- [ ] **Step 3: Append diff-inspection guidance to both repair prompts**

To both `logical/prompts/repair.md` and `physical/prompts/repair.md`, append (before the final-message constraint from Chunk 1):

```markdown

## Incremental Repair

Before authoring a new mutation file, call `inspect_graph(view="diff", against="previous_attempt")` to see what the last successful mutation already accomplished. Only encode the deltas the current evaluation report requires — do not rewrite the whole graph.
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/stages/test_prompts_surface.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/trace/stages/logical/prompts/repair.md src/trace/stages/physical/prompts/repair.md tests/unit/stages/test_prompts_surface.py
git commit -m "docs(repair): instruct agents to diff-against-previous-attempt before authoring"
```

### Task 2.9: Verify full test suite and demo smoke

- [ ] **Step 1: Full unit suite**

Run: `pytest -q`
Expected: all green.

- [ ] **Step 2: Demo smoke**

```powershell
$env:LANGSMITH_TRACING="false"
trace run tests/demo/demo.md --run-id pr2-smoke-001 --output-root runs
```

Expected:
- `runs/pr2-smoke-001/run.json` `status` is `completed`.
- `runs/pr2-smoke-001/logical/repair_history.json` (if any rounds exist) every entry has a `produced_files` array.
- `runs/pr2-smoke-001/physical/mutations/snapshots/attempt_1.json` exists for the first successful build mutation.
- LangSmith trace (if re-enabled) shows `inspect_graph` calls with `view="diff"` during repair rounds.

- [ ] **Step 3: Branch / PR**

Open PR titled `feat: PR2 ledger product-pointers and mutation incrementality`. Reference spec modules E + F.

PR2 chunk done.

---

## Chunk 3: PR3 — LangGraph Native Convergence (Reducers, Command Routing, ChatOpenAI Cache)

This chunk swaps hand-rolled state plumbing for LangGraph 1.x native idioms. After PR3 merges, all list fields accumulate via reducer; validator/evaluator nodes return `Command(...)`; `ChatOpenAI` instances are cached.

**Branch / commit cadence:** ~10 commits. This chunk is more invasive than PR1/PR2; run the full suite after each task.

### Task 3.1: Annotate `RunState` list fields with reducers

**Files:**
- Modify: `src/trace/runtime/engine.py` (`RunState`)
- Modify: `src/trace/runtime/reducers.py` (`merge_run_state` no longer concats events)
- Create test: `tests/unit/runtime/test_reducers.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/runtime/test_reducers.py
from langgraph.graph import END, StateGraph
from trace.runtime.engine import RunState


def test_run_state_events_accumulate_via_reducer():
    graph = StateGraph(RunState)
    graph.add_node("node_a", lambda state: {"events": [{"type": "a"}]})
    graph.add_node("node_b", lambda state: {"events": [{"type": "b"}]})
    graph.set_entry_point("node_a")
    graph.add_edge("node_a", "node_b")
    graph.add_edge("node_b", END)
    compiled = graph.compile()
    result = compiled.invoke({"run_id": "test", "intent": "x", "status": "running"})
    types = [event["type"] for event in result.get("events", [])]
    assert types == ["a", "b"]


def test_escalation_history_accumulates_via_reducer():
    graph = StateGraph(RunState)
    graph.add_node("node_a", lambda state: {"escalation_history": [{"round": 1}]})
    graph.add_node("node_b", lambda state: {"escalation_history": [{"round": 2}]})
    graph.set_entry_point("node_a")
    graph.add_edge("node_a", "node_b")
    graph.add_edge("node_b", END)
    compiled = graph.compile()
    result = compiled.invoke({"run_id": "t", "intent": "x", "status": "running"})
    rounds = [item["round"] for item in result.get("escalation_history", [])]
    assert rounds == [1, 2]
```

- [ ] **Step 2: Run test to verify fail**

Run: `pytest tests/unit/runtime/test_reducers.py -v`
Expected: FAIL — `events` currently overwrites instead of accumulating; `escalation_history` field doesn't exist.

- [ ] **Step 3: Annotate `RunState` fields**

In `src/trace/runtime/engine.py`:

```python
import operator
from typing import Annotated, Any, TypedDict


class RunState(TypedDict, total=False):
    run_id: str
    intent: str
    status: str
    current_stage: str | None
    artifacts: dict[str, dict[str, Any]]
    stage_reports: dict[str, dict[str, Any]]
    attempt_counters: dict[str, int]
    support_files: dict[str, str]
    events: Annotated[list[dict[str, Any]], operator.add]
    escalation_history: Annotated[list[dict[str, Any]], operator.add]
    error: dict[str, Any] | None
    config_snapshot: dict[str, Any]
    resume: dict[str, Any]
```

- [ ] **Step 4: Drop events concat from `merge_run_state`**

In `src/trace/runtime/reducers.py`:

```python
def merge_run_state(current: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(current)

    for field in ("status", "current_stage", "error", "config_snapshot", "run_id", "intent"):
        if field in update:
            merged[field] = deepcopy(update[field])

    merged["artifacts"] = _merge_dict(merged.get("artifacts", {}), update.get("artifacts", {}))
    merged["attempt_counters"] = _merge_dict(merged.get("attempt_counters", {}), update.get("attempt_counters", {}))
    merged["stage_reports"] = _merge_dict(merged.get("stage_reports", {}), update.get("stage_reports", {}))
    merged["support_files"] = _merge_dict(merged.get("support_files", {}), update.get("support_files", {}))
    # NOTE: events and escalation_history are reducer-managed (Annotated[list, operator.add]);
    # callers should return partial updates and let LangGraph accumulate.
    return merged
```

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/unit/runtime/test_reducers.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/trace/runtime/engine.py src/trace/runtime/reducers.py tests/unit/runtime/test_reducers.py
git commit -m "feat(runtime): annotate RunState list fields with reducers"
```

### Task 3.2: Annotate stage TypedDict list fields with reducers; remove `next_action`

**Files:**
- Modify: `src/trace/stages/ground/state.py`
- Modify: `src/trace/stages/logical/state.py`
- Modify: `src/trace/stages/physical/state.py`
- Test: `tests/unit/runtime/test_reducers.py` (extend)

- [ ] **Step 1: Extend test for stage states**

Append to `tests/unit/runtime/test_reducers.py`:

```python
def test_logical_state_repair_history_accumulates():
    from langgraph.graph import END, StateGraph
    from trace.stages.logical.state import LogicalState

    graph = StateGraph(LogicalState)
    graph.add_node("a", lambda state: {"repair_history": [{"round": 1}]})
    graph.add_node("b", lambda state: {"repair_history": [{"round": 2}]})
    graph.set_entry_point("a")
    graph.add_edge("a", "b")
    graph.add_edge("b", END)
    compiled = graph.compile()
    result = compiled.invoke({})
    rounds = [item["round"] for item in result.get("repair_history", [])]
    assert rounds == [1, 2]


def test_ground_state_does_not_define_next_action():
    from trace.stages.ground.state import GroundState
    assert "next_action" not in GroundState.__optional_keys__


def test_logical_state_does_not_define_next_action():
    from trace.stages.logical.state import LogicalState
    assert "next_action" not in LogicalState.__optional_keys__


def test_physical_state_does_not_define_next_action():
    from trace.stages.physical.state import PhysicalState
    assert "next_action" not in PhysicalState.__optional_keys__
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/unit/runtime/test_reducers.py -v`
Expected: FAIL.

- [ ] **Step 3: Update three stage state files**

In `src/trace/stages/logical/state.py`:

```python
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class LogicalState(TypedDict, total=False):
    ground_artifact: dict[str, Any]
    attempt: int
    max_attempts: int
    author_output: dict[str, Any]
    draft_artifact: dict[str, Any]
    logical_artifact: dict[str, Any]
    evaluation_report: dict[str, Any]
    repair_history: Annotated[list[dict[str, Any]], operator.add]
    messages: list[dict[str, str]]
    events: Annotated[list[dict[str, Any]], operator.add]
    support_files: dict[str, str]
    support_file_root: str
    result: dict[str, Any]
    error: dict[str, Any] | None
```

(Drop `next_action`.)

In `src/trace/stages/physical/state.py`: same shape for `PhysicalState` — `repair_history` and `events` annotated, `next_action` dropped.

In `src/trace/stages/ground/state.py`:

```python
class GroundState(TypedDict, total=False):
    intent: str
    grounding_checks: dict[str, Any]
    attempt: int
    max_attempts: int
    status: str
    draft_artifact: dict[str, Any]
    evaluation_report: dict[str, Any]
    messages: list[dict[str, str]]
    retry_history: Annotated[list[dict[str, Any]], operator.add]
    events: Annotated[list[dict[str, Any]], operator.add]
    support_files: dict[str, str]
    support_file_root: str
    result: dict[str, Any]
    error: dict[str, Any] | None
```

(Drop `next_action`.)

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/runtime/test_reducers.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/trace/stages/ground/state.py src/trace/stages/logical/state.py src/trace/stages/physical/state.py tests/unit/runtime/test_reducers.py
git commit -m "refactor(state): annotate stage list fields; remove next_action"
```

### Task 3.3: Refactor `_merge_stage_result` / `_merge_stage_exception` to return partial updates

**Files:**
- Modify: `src/trace/runtime/engine.py`
- Modify existing tests under `tests/integration/test_runtime_pipeline.py` if they assert on the merge-side behavior

- [ ] **Step 1: Update `_merge_stage_result`**

Change the function signature: it should now return a partial state dict that LangGraph will merge via reducers. Keep storage side effects.

```python
def _merge_stage_result(self, state: RunState, stage_id: str, result: dict[str, Any]) -> dict[str, Any]:
    partial: dict[str, Any] = {
        "current_stage": stage_id,
        "artifacts": {**state.get("artifacts", {}), stage_id: result["artifact"]},
        "stage_reports": {
            **state.get("stage_reports", {}),
            stage_id: {
                "stage_id": stage_id,
                "attempts_used": result["attempts_used"],
                "evaluation_summary": result["evaluation_summary"],
            },
        },
        "attempt_counters": {**state.get("attempt_counters", {}), stage_id: result["attempts_used"]},
        "support_files": {**state.get("support_files", {}), **result.get("support_files", {})},
        # NOTE: events are reducer-accumulated; return only the new ones.
        "events": result["events"],
    }
    self.storage.write_run_state(run_id=state["run_id"], run_payload={**state, **partial})
    self.storage.write_stage_snapshot(
        run_id=state["run_id"],
        stage_id=stage_id,
        artifact=result["artifact"],
        evaluation=result["evaluation_summary"] or {"ok": True, "issues": []},
        summary={"attempts_used": result["attempts_used"]},
        messages=result["messages"],
        tool_journal=result["tool_journal"],
        history_name=_stage_history_name(stage_id),
        history_entries=result[_stage_history_name(stage_id)],
        events=result["events"],
        support_files=result.get("support_files", {}),
    )
    return partial


def _merge_stage_exception(self, state: RunState, stage_id: str, exc: Exception) -> dict[str, Any]:
    error = {"stage_id": stage_id, "type": type(exc).__name__, "message": str(exc)}
    partial = {
        "status": "failed",
        "current_stage": stage_id,
        "error": error,
        "events": [{"type": "run.stage_failed", "stage_id": stage_id, "error": error}],
    }
    merged = {**state, **partial}
    self.storage.write_run_state(run_id=merged["run_id"], run_payload=merged)
    self.storage.write_stage_snapshot(
        run_id=merged["run_id"],
        stage_id=stage_id,
        artifact=merged.get("artifacts", {}).get(stage_id, {}),
        evaluation={"ok": False, "issues": []},
        summary={"attempts_used": 0, "error": error},
        messages=[],
        tool_journal=[],
        history_name=_stage_history_name(stage_id),
        history_entries=[],
        events=partial["events"],
        support_files={},
    )
    return partial


def _finalize(self, state: RunState) -> dict[str, Any]:
    return {
        "status": "completed",
        "current_stage": None,
        "events": [{"type": "run.completed"}],
    }
```

- [ ] **Step 2: Run integration suite**

Run: `pytest tests/integration -v`
Expected: PASS (any failures here mean a test asserted on the now-deprecated merge behavior; update accordingly to assert on final state shape only).

- [ ] **Step 3: Commit**

```bash
git add src/trace/runtime/engine.py tests/integration
git commit -m "refactor(engine): return partial stage updates and rely on RunState reducers"
```

### Task 3.4: Refactor all stage nodes to return partial updates (logical stage)

**Files:**
- Modify: `src/trace/stages/logical/nodes/author.py`, `builder.py`, `prepare.py`, `repair.py`, `finalize.py`
- Modify existing logical stage unit tests (if any assert specific `state["events"]` overwrite semantics)

- [ ] **Step 1: Inventory event-append patterns in logical nodes**

Run: `rg -n "state\[\"events\"\] = \[\*state.get|state\[\"repair_history\"\] = \[\*" src/trace/stages/logical/nodes`
Capture every match.

- [ ] **Step 2: Refactor each logical node to return partial**

For each `node(state)` function:

a. Stop assigning to `state[key]` for reducer-managed fields (`events`, `repair_history`).
b. Build a partial dict and return it. LangGraph merges it via the state schema (reducers for annotated fields, default replace for others).

Example (`logical/nodes/repair.py`):

```python
def repair_node(state: LogicalState, role_client) -> dict[str, Any]:
    prior_ledger = list(state.get("repair_history", []))
    repair_tools = StageRepairTools(
        state["draft_artifact"],
        support_files=state.get("support_files", {}),
        support_file_root=state.get("support_file_root"),
        mutation_index_seed=len(prior_ledger) + 1,
    )
    messages = _build_repair_messages(...)
    agent_result = role_client.invoke_agent(
        role_name="logical_repair",
        messages=messages,
        tools=repair_tools.as_agent_tools(),
        max_react_steps=MAX_REACT_STEPS,
    )
    post_repair_report = repair_tools.validate_graph()
    ledger_entry = _build_repair_ledger_entry(
        round_index=len(prior_ledger) + 1,
        issues_before=state["evaluation_report"],
        issues_after=post_repair_report,
        attempted_actions=_extract_tool_attempts(agent_result),
    )
    return {
        "draft_artifact": repair_tools.artifact_state(),
        "support_files": repair_tools.support_files(),
        "messages": _extract_messages(agent_result),
        "attempt": state.get("attempt", 0) + 1,
        # reducer-appended; do NOT concat with prior:
        "repair_history": [ledger_entry],
        "events": [{"type": "logical.repair.completed", "attempt": state.get("attempt", 0) + 1}],
    }
```

(Note: `mutation_index_seed` is now `len(prior_ledger) + 1` to match Chunk 2.6.)

Apply the same partial-return pattern to:
- `prepare_node` — was returning full state mutation; now return only the new keys.
- `author_node` — return only `{"author_output", "messages", "events": [...]}` etc.
- `builder_node` — return only `{"draft_artifact", "support_files", "messages", "events": [...]}`.
- `finalize_node` — return only `{"result", "events": [...]}` or similar.

- [ ] **Step 3: Run logical stage tests**

Run: `pytest tests/unit/stages/logical tests/unit/stages/test_filtered_read_tools.py tests/unit/stages/test_repair_tools_summary.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/trace/stages/logical/nodes
git commit -m "refactor(logical): nodes return partial updates; reducer-managed lists"
```

### Task 3.5: Refactor physical stage nodes to return partial updates

**Files:**
- Modify: `src/trace/stages/physical/nodes/author.py`, `builder.py`, `prepare.py`, `repair.py`, `finalize.py`

- [ ] **Step 1: Mirror the logical-stage refactor**

Same pattern as Task 3.4 for physical nodes. Pay attention to two physical-only details:

- `physical/nodes/repair.py` already received the `image_catalog` cleanup (Chunk 1 Task 1.9). Re-confirm imports are tidy.
- `physical/nodes/validator.py` is converted to `Command` in Task 3.7; leave it alone in this task.

- [ ] **Step 2: Run physical stage tests**

Run: `pytest tests/unit/stages/physical -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add src/trace/stages/physical/nodes
git commit -m "refactor(physical): nodes return partial updates"
```

### Task 3.6: Refactor ground stage nodes to return partial updates

**Files:**
- Modify: `src/trace/stages/ground/nodes/*.py` (excluding `evaluator.py` which is handled in Task 3.7)

- [ ] **Step 1: Apply same pattern**

For each ground node `node(state)`, change `state[...] = ...` assignments for reducer-managed fields to partial-dict return. `retry_history` and `events` are reducer-managed; `messages` is not (overwrite is intended).

- [ ] **Step 2: Run ground stage tests**

Run: `pytest tests/unit/stages -k ground -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add src/trace/stages/ground/nodes
git commit -m "refactor(ground): nodes return partial updates"
```

### Task 3.7: Convert validator and evaluator to `Command`-based routing

**Files:**
- Modify: `src/trace/stages/logical/nodes/validator.py`
- Modify: `src/trace/stages/physical/nodes/validator.py`
- Modify: `src/trace/stages/ground/nodes/evaluator.py`
- Modify: `src/trace/stages/logical/__init__.py`, `physical/__init__.py`, `ground/__init__.py` (drop `add_conditional_edges` for these branches; LangGraph reads routing from the returned `Command`)
- Create test: `tests/unit/stages/test_validator_command.py`
- Create test: `tests/unit/stages/test_evaluator_command.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/stages/test_validator_command.py
from langgraph.types import Command
from trace.stages.logical.nodes.validator import validator_node as logical_validator
from trace.stages.physical.nodes.validator import validator_node as physical_validator


def test_logical_validator_returns_command_finalize_when_ok(monkeypatch):
    monkeypatch.setattr(
        "trace.stages.logical.nodes.validator._validate_logical_artifact",
        lambda *_args, **_kwargs: {"ok": True, "issues": []},
    )
    state = {"draft_artifact": {"graph": {}}, "attempt": 1, "max_attempts": 3}
    result = logical_validator(state)
    assert isinstance(result, Command)
    assert result.goto == "finalize"
    assert result.update.get("evaluation_report") == {"ok": True, "issues": []}


def test_logical_validator_returns_command_repair_when_not_ok(monkeypatch):
    monkeypatch.setattr(
        "trace.stages.logical.nodes.validator._validate_logical_artifact",
        lambda *_args, **_kwargs: {"ok": False, "issues": [{"details": {"issue_kind": "missing_link"}}]},
    )
    state = {"draft_artifact": {"graph": {}}, "attempt": 1, "max_attempts": 3}
    result = logical_validator(state)
    assert result.goto == "repair"


def test_logical_validator_returns_command_failed_when_attempts_exhausted(monkeypatch):
    monkeypatch.setattr(
        "trace.stages.logical.nodes.validator._validate_logical_artifact",
        lambda *_args, **_kwargs: {"ok": False, "issues": [{"details": {"issue_kind": "missing_link"}}]},
    )
    state = {"draft_artifact": {"graph": {}}, "attempt": 3, "max_attempts": 3}
    result = logical_validator(state)
    from langgraph.graph import END
    assert result.goto == END
    assert result.update.get("error") is not None
```

(Add similar tests for physical_validator and ground evaluator.)

- [ ] **Step 2: Run tests to verify fail**

Run: `pytest tests/unit/stages/test_validator_command.py -v`
Expected: FAIL.

- [ ] **Step 3: Convert validator/evaluator nodes**

In `src/trace/stages/logical/nodes/validator.py`:

```python
from langgraph.graph import END
from langgraph.types import Command


def validator_node(state: LogicalState) -> Command:
    report = _validate_logical_artifact(...)
    if report["ok"]:
        return Command(goto="finalize", update={"evaluation_report": report})
    if state["attempt"] >= state["max_attempts"]:
        return Command(
            goto=END,
            update={
                "evaluation_report": report,
                "error": {"message": "logical stage exceeded max attempts", "issues": report["issues"]},
            },
        )
    return Command(goto="repair", update={"evaluation_report": report})
```

Same shape for `physical/nodes/validator.py` and `ground/nodes/evaluator.py`.

- [ ] **Step 4: Drop `add_conditional_edges` for these branches in stage `__init__.py`**

In `src/trace/stages/logical/__init__.py`:

```python
def _build_logical_graph(*, role_client, settings):
    del settings
    graph = StateGraph(LogicalState)
    graph.add_node("prepare", prepare_node)
    graph.add_node("author", lambda state: author_node(state, role_client))
    graph.add_node("builder", lambda state: builder_node(state, role_client))
    graph.add_node("validator", validator_node)
    graph.add_node("repair", lambda state: repair_node(state, role_client))
    graph.add_node("finalize", finalize_node)
    graph.set_entry_point("prepare")
    graph.add_edge("prepare", "author")
    graph.add_edge("author", "builder")
    graph.add_edge("builder", "validator")
    # validator returns Command(goto=...); LangGraph reads it directly.
    graph.add_edge("repair", "validator")
    graph.add_edge("finalize", END)
    return graph.compile()
```

Same drop for physical and ground.

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/unit/stages -v`
Expected: PASS. If any old test still asserts `state["next_action"]`, update to assert on `Command.goto` or on final state.

- [ ] **Step 6: Commit**

```bash
git add src/trace/stages tests/unit/stages
git commit -m "feat(stages): validator and evaluator return Command for routing"
```

### Task 3.8: Cache `ChatOpenAI` instances in `LangChainRoleClient`

**Files:**
- Modify: `src/trace/runtime/role_client.py`
- Create test: `tests/unit/runtime/test_role_client_cache.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/runtime/test_role_client_cache.py
from unittest.mock import patch
from trace.config.settings import RoleSettings, TraceSettings, LangSmithSettings
from trace.runtime.role_client import LangChainRoleClient


def _stub_settings():
    return TraceSettings(
        openai_api_key="sk-test",
        openai_base_url="https://example/v1",
        langsmith=LangSmithSettings(),
        roles={
            "logical_repair": RoleSettings(model="gpt-4o-mini", temperature=0.0, max_attempts=3),
        },
    )


def test_chat_openai_cached_for_same_role_signature():
    settings = _stub_settings()
    client = LangChainRoleClient(settings)
    with patch("trace.runtime.role_client.ChatOpenAI") as ChatOpenAIMock:
        ChatOpenAIMock.return_value = object()
        client._chat_openai(role_name="logical_repair")
        client._chat_openai(role_name="logical_repair")
        assert ChatOpenAIMock.call_count == 1


def test_chat_openai_distinct_role_creates_separate_instance():
    settings = _stub_settings()
    settings.roles["logical_author"] = RoleSettings(model="gpt-4o", temperature=0.2, max_attempts=3)
    client = LangChainRoleClient(settings)
    with patch("trace.runtime.role_client.ChatOpenAI") as ChatOpenAIMock:
        ChatOpenAIMock.return_value = object()
        client._chat_openai(role_name="logical_repair")
        client._chat_openai(role_name="logical_author")
        assert ChatOpenAIMock.call_count == 2
```

- [ ] **Step 2: Run test to verify fail**

Run: `pytest tests/unit/runtime/test_role_client_cache.py -v`
Expected: FAIL — `_chat_openai` doesn't exist and ChatOpenAI is re-instantiated on every call.

- [ ] **Step 3: Implement cache helper**

In `src/trace/runtime/role_client.py`:

```python
class LangChainRoleClient:
    def __init__(self, settings: TraceSettings, observer: TraceObserver | None = None) -> None:
        self.settings = settings
        self.observer = observer or TraceObserver(settings.langsmith)
        self._chat_openai_cache: dict[tuple[str, str, float, str], ChatOpenAI] = {}

    def _chat_openai(self, *, role_name: str) -> ChatOpenAI:
        role_settings = self.settings.roles[role_name]
        cache_key = (role_name, role_settings.model, role_settings.temperature, self.settings.openai_base_url or "")
        cached = self._chat_openai_cache.get(cache_key)
        if cached is not None:
            return cached
        model = ChatOpenAI(
            model=role_settings.model,
            temperature=role_settings.temperature,
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
        )
        self._chat_openai_cache[cache_key] = model
        return model
```

Replace every `ChatOpenAI(...)` instantiation in `invoke_structured`, `invoke_agent`, `invoke` with `self._chat_openai(role_name=role_name)`.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/runtime/test_role_client_cache.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/trace/runtime/role_client.py tests/unit/runtime/test_role_client_cache.py
git commit -m "feat(role_client): cache ChatOpenAI instances by role signature"
```

### Task 3.9: Rename `max_tool_calls` → `max_react_steps` with semantic clarification

**Files:**
- Modify: `src/trace/runtime/role_client.py`
- Modify: `src/trace/stages/logical/nodes/author.py`, `builder.py`, `repair.py` (call sites + `MAX_TOOL_CALLS` constant rename)
- Modify: `src/trace/stages/physical/nodes/author.py`, `builder.py`, `repair.py` (same)
- Modify: all test files invoking `invoke_agent(..., max_tool_calls=...)`

- [ ] **Step 1: Inventory call sites**

Run: `rg -n "max_tool_calls|MAX_TOOL_CALLS" src/trace tests`
Capture every match.

- [ ] **Step 2: Rename in `role_client.py`**

```python
def invoke_agent(
    self,
    *,
    role_name: str,
    messages: list[dict[str, str]],
    tools: list[Any],
    max_react_steps: int = 24,
    max_tool_calls: int | None = None,  # backwards-compatible alias for one PR
) -> Any:
    if max_tool_calls is not None:
        # Deprecated alias kept temporarily; treat as max_react_steps.
        max_react_steps = max_tool_calls
    role_settings = self.settings.roles[role_name]
    with self.observer.role_run(role_name, message_count=len(messages), tool_count=len(tools)):
        model = self._chat_openai(role_name=role_name)
        agent = create_react_agent(model, tools, prompt=None)
        lc_messages = [_to_message(item) for item in messages]
        # recursion_limit maps to LangGraph steps; each react cycle costs 2 (model + tool).
        return agent.invoke({"messages": lc_messages}, {"recursion_limit": max_react_steps * 2})
```

(If the pinned langgraph version exposes `max_steps` on `create_react_agent`, prefer that — the body becomes `agent = create_react_agent(model, tools, prompt=None, max_steps=max_react_steps)`. Check the installed version with `pip show langgraph | findstr Version`; document the chosen branch in code comment.)

- [ ] **Step 3: Rename `MAX_TOOL_CALLS` constants to `MAX_REACT_STEPS` (and adjust default values if appropriate)**

In each of the 6 node files:

```python
MAX_REACT_STEPS = 12
```

Update each `invoke_agent(role_name=..., messages=..., tools=..., max_tool_calls=MAX_TOOL_CALLS)` to `invoke_agent(role_name=..., messages=..., tools=..., max_react_steps=MAX_REACT_STEPS)`.

- [ ] **Step 4: Update existing tests that pass `max_tool_calls=12` in `FakeRoleClient.invoke_agent` signatures**

For each `class FakeRoleClient` definition in `tests/unit/stages/**`, change `max_tool_calls=12` parameter to `max_react_steps=12` (keep `max_tool_calls` as a backwards-compat alias only in production code, not in tests).

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/trace tests/unit
git commit -m "refactor(role_client): rename max_tool_calls to max_react_steps with clarified semantics"
```

### Task 3.10: Verify full test suite and demo smoke

- [ ] **Step 1: Full unit + integration suite**

Run: `pytest -q`
Expected: all green.

- [ ] **Step 2: Demo smoke**

```powershell
$env:LANGSMITH_TRACING="false"
trace run tests/demo/demo.md --run-id pr3-smoke-001 --output-root runs
```

Expected:
- Run completes.
- `runs/pr3-smoke-001/events.jsonl` contains the full event stream (reducer-accumulated correctly).
- `repair_history` events appended in order across rounds without duplicates.

- [ ] **Step 3: Branch / PR**

Open PR titled `feat: PR3 LangGraph native convergence (reducers, Command, ChatOpenAI cache)`. Reference spec module C1+C2.

PR3 chunk done.

---

## Chunk 4: PR4 — SqliteSaver Checkpointer + Escalation Reverse Channel

This chunk lands the two highest-risk pieces of the spec in one PR because they share the same RunState mutation surface (`escalation_history`, `attempt_counters["escalation"]`, sqlite-aware resume path). After PR4 merges, the runtime is fully aligned with the spec.

**Branch / commit cadence:** ~12 commits. Run the full suite + a synthesized escalation smoke after each task.

### Task 4.1: Add `langgraph-checkpoint-sqlite` dependency and gitignore

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`

- [ ] **Step 1: Inventory current langgraph pins**

Run: `rg -n "langgraph" pyproject.toml`
Capture pinned versions to choose a compatible `langgraph-checkpoint-sqlite` release.

- [ ] **Step 2: Add dependency**

In `pyproject.toml` under `[project] dependencies` (or matching list):

```toml
"langgraph-checkpoint-sqlite>=2.0.0,<3.0.0",
```

Pin range must be compatible with the existing `langgraph>=1.x` pin. Update the lower bound to whatever the matching release notes call out for `langgraph` 1.x; this plan uses 2.0.0 as a placeholder — verify on PyPI before commit.

- [ ] **Step 3: Append to `.gitignore`**

```
runs/*/state.sqlite
runs/*/state.sqlite-*
```

(The second line catches SQLite WAL/SHM sidecar files.)

- [ ] **Step 4: Install and verify import**

Run (PowerShell):

```powershell
pip install -e .
python -c "from langgraph.checkpoint.sqlite import SqliteSaver; print(SqliteSaver)"
```

Expected: prints the class.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore
git commit -m "build: add langgraph-checkpoint-sqlite dependency"
```

### Task 4.2: Define escalation constants and helpers

**Files:**
- Create: `src/trace/runtime/escalation.py`
- Create test: `tests/unit/runtime/test_escalation.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/runtime/test_escalation.py
from trace.runtime.escalation import (
    ESCALATION_TO_GROUND_KINDS,
    extract_escalation_issues,
    build_escalation_report,
)


def test_white_list_includes_documented_kinds():
    assert ESCALATION_TO_GROUND_KINDS == frozenset({
        "logical.escalation.constraint_conflict",
        "logical.escalation.no_satisfying_topology",
        "physical.escalation.no_satisfying_image",
        "physical.escalation.no_satisfying_flavor",
    })


def test_extract_escalation_issues_filters_by_kind():
    report = {
        "issues": [
            {"details": {"issue_kind": "logical.escalation.constraint_conflict", "summary": "A vs B"}},
            {"details": {"issue_kind": "logical.missing_link"}},
            {"details": {"issue_kind": "physical.escalation.no_satisfying_image"}},
        ]
    }
    matched = extract_escalation_issues(report)
    kinds = [item["details"]["issue_kind"] for item in matched]
    assert kinds == ["logical.escalation.constraint_conflict", "physical.escalation.no_satisfying_image"]


def test_extract_escalation_issues_empty_when_no_matches():
    report = {"issues": [{"details": {"issue_kind": "logical.missing_link"}}]}
    assert extract_escalation_issues(report) == []


def test_build_escalation_report_shape():
    report = {"issues": [{"details": {"issue_kind": "logical.escalation.constraint_conflict", "summary": "A vs B"}}]}
    partial_artifact = {"graph": {"nodes": []}}
    payload = build_escalation_report(
        stage_id="logical",
        report=report,
        partial_artifact=partial_artifact,
        attempt=3,
    )
    assert payload["source_stage"] == "logical"
    assert payload["attempt_at_escalation"] == 3
    assert payload["issues"] == report["issues"]  # full forwarding; ground decides how much to surface
    assert payload["partial_artifact"] == partial_artifact
```

- [ ] **Step 2: Run test to verify fail**

Run: `pytest tests/unit/runtime/test_escalation.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `escalation.py`**

```python
# src/trace/runtime/escalation.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


ESCALATION_TO_GROUND_KINDS: frozenset[str] = frozenset({
    "logical.escalation.constraint_conflict",
    "logical.escalation.no_satisfying_topology",
    "physical.escalation.no_satisfying_image",
    "physical.escalation.no_satisfying_flavor",
})


def extract_escalation_issues(report: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not report:
        return []
    matches: list[dict[str, Any]] = []
    for issue in report.get("issues", []) or []:
        details = issue.get("details") if isinstance(issue, dict) else None
        if not isinstance(details, dict):
            continue
        if details.get("issue_kind") in ESCALATION_TO_GROUND_KINDS:
            matches.append(issue)
    return matches


def build_escalation_report(
    *,
    stage_id: str,
    report: dict[str, Any],
    partial_artifact: dict[str, Any] | None,
    attempt: int,
) -> dict[str, Any]:
    return {
        "source_stage": stage_id,
        "attempt_at_escalation": attempt,
        "issues": list(report.get("issues", []) or []),
        "notes": list(report.get("notes", []) or []),
        "partial_artifact": partial_artifact or {},
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/runtime/test_escalation.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/trace/runtime/escalation.py tests/unit/runtime/test_escalation.py
git commit -m "feat(runtime): escalation kind white-list and helpers"
```

### Task 4.3: Extend `GroundState` and `GroundDraftArtifact` for escalation

**Files:**
- Modify: `src/trace/stages/ground/state.py`
- Modify: `src/trace/stages/ground/schemas.py`
- Test: `tests/unit/stages/test_ground_escalation_mode.py` (created in Task 4.5; here just verify schema)

- [ ] **Step 1: Update `GroundState`**

In `src/trace/stages/ground/state.py`:

```python
class GroundState(TypedDict, total=False):
    intent: str
    grounding_checks: dict[str, Any]
    attempt: int
    max_attempts: int
    status: str
    draft_artifact: dict[str, Any]
    evaluation_report: dict[str, Any]
    messages: list[dict[str, str]]
    retry_history: Annotated[list[dict[str, Any]], operator.add]
    events: Annotated[list[dict[str, Any]], operator.add]
    support_files: dict[str, str]
    support_file_root: str
    result: dict[str, Any]
    error: dict[str, Any] | None
    escalation_report: dict[str, Any] | None
    unsolvable_notes: list[str]
```

- [ ] **Step 2: Update `GroundDraftArtifact`**

Find the model definition in `src/trace/stages/ground/schemas.py`. Add (alongside existing fields):

```python
class GroundDraftArtifact(BaseModel):
    # ... existing fields ...
    unsolvable: bool = False
    unsolvable_reason: str | None = None
```

Run: `rg -n "class GroundDraftArtifact" src/trace/stages/ground` to locate.

- [ ] **Step 3: Smoke test**

Run: `python -c "from trace.stages.ground.schemas import GroundDraftArtifact; a = GroundDraftArtifact(intent='x', node_groups=[], logical_constraints=[], physical_constraints=[], unsolvable=True, unsolvable_reason='r'); print(a.unsolvable)"`
Expected: prints `True`.

(If the model has required fields beyond these, adapt the smoke call.)

- [ ] **Step 4: Run ground stage tests**

Run: `pytest tests/unit/stages -k ground -v`
Expected: PASS — existing tests don't assert against new optional fields.

- [ ] **Step 5: Commit**

```bash
git add src/trace/stages/ground/state.py src/trace/stages/ground/schemas.py
git commit -m "feat(ground): add escalation_report state and unsolvable schema fields"
```

### Task 4.4: Convert stage validators to recognize escalation issue kinds

**Files:**
- Modify: `src/trace/stages/logical/nodes/validator.py`
- Modify: `src/trace/stages/physical/nodes/validator.py`
- Modify: `src/trace/stages/logical/__init__.py`, `physical/__init__.py` (add `escalate` node)
- Create test: `tests/unit/stages/test_validator_escalation.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/stages/test_validator_escalation.py
from langgraph.graph import END
from langgraph.types import Command


def _physical_state(*, attempt=1, max_attempts=3, issue_kind="physical.escalation.no_satisfying_image"):
    return {
        "logical_artifact": {"graph": {"nodes": [], "links": []}},
        "draft_artifact": {"graph": {"nodes": [], "links": []}},
        "attempt": attempt,
        "max_attempts": max_attempts,
        # injected by monkeypatched _validate_physical_artifact below
    }


def test_physical_validator_routes_to_escalate_when_kind_matches(monkeypatch):
    from trace.stages.physical.nodes.validator import validator_node

    monkeypatch.setattr(
        "trace.stages.physical.nodes.validator._validate_physical_artifact",
        lambda *_args, **_kwargs: {
            "ok": False,
            "issues": [{"details": {"issue_kind": "physical.escalation.no_satisfying_image"}}],
        },
    )
    result = validator_node(_physical_state(attempt=1, max_attempts=3))
    assert isinstance(result, Command)
    assert result.goto == "escalate"
    assert result.update.get("evaluation_report")["issues"][0]["details"]["issue_kind"] == "physical.escalation.no_satisfying_image"


def test_physical_validator_prefers_escalate_when_attempts_exhausted_and_kind_matches(monkeypatch):
    from trace.stages.physical.nodes.validator import validator_node

    monkeypatch.setattr(
        "trace.stages.physical.nodes.validator._validate_physical_artifact",
        lambda *_args, **_kwargs: {
            "ok": False,
            "issues": [{"details": {"issue_kind": "physical.escalation.no_satisfying_image"}}],
        },
    )
    # Per spec: even when attempts exhausted, escalation kind still routes to escalate.
    result = validator_node(_physical_state(attempt=3, max_attempts=3))
    assert result.goto == "escalate"


def test_physical_validator_falls_back_to_failed_when_attempts_exhausted_without_escalation_kind(monkeypatch):
    from trace.stages.physical.nodes.validator import validator_node

    monkeypatch.setattr(
        "trace.stages.physical.nodes.validator._validate_physical_artifact",
        lambda *_args, **_kwargs: {
            "ok": False,
            "issues": [{"details": {"issue_kind": "physical.missing_field"}}],
        },
    )
    result = validator_node(_physical_state(attempt=3, max_attempts=3))
    assert result.goto == END
    assert result.update.get("error") is not None


def test_physical_validator_does_not_escalate_when_ok(monkeypatch):
    from trace.stages.physical.nodes.validator import validator_node

    monkeypatch.setattr(
        "trace.stages.physical.nodes.validator._validate_physical_artifact",
        lambda *_args, **_kwargs: {"ok": True, "issues": []},
    )
    result = validator_node(_physical_state(attempt=1, max_attempts=3))
    assert result.goto == "finalize"


def test_logical_validator_routes_to_escalate_when_kind_matches(monkeypatch):
    from trace.stages.logical.nodes.validator import validator_node

    monkeypatch.setattr(
        "trace.stages.logical.nodes.validator._validate_logical_artifact",
        lambda *_args, **_kwargs: {
            "ok": False,
            "issues": [{"details": {"issue_kind": "logical.escalation.constraint_conflict"}}],
        },
    )
    state = {"draft_artifact": {"graph": {}}, "attempt": 1, "max_attempts": 3}
    result = validator_node(state)
    assert result.goto == "escalate"
```

- [ ] **Step 2: Run tests to verify fail**

Run: `pytest tests/unit/stages/test_validator_escalation.py -v`
Expected: FAIL — `escalate` branch doesn't exist; old validator returns `Command(goto="repair")` or `END` for these inputs.

- [ ] **Step 3: Update `physical/nodes/validator.py` precedence**

```python
from langgraph.graph import END
from langgraph.types import Command

from trace.runtime.escalation import build_escalation_report, extract_escalation_issues
from trace.stages.physical.state import PhysicalState


def validator_node(state: PhysicalState) -> Command:
    report = _validate_physical_artifact(
        artifact=state["draft_artifact"],
        logical_graph=state["logical_artifact"]["graph"],
        state=state,
    )
    if report["ok"]:
        return Command(goto="finalize", update={"evaluation_report": report})

    escalation_issues = extract_escalation_issues(report)
    attempts_exhausted = state["attempt"] >= state["max_attempts"]
    # Precedence per spec module G:
    # - escalation kinds always route to escalate (independent of attempt budget),
    #   because these issues are not agent-fixable by repair.
    # - otherwise, attempts exhausted → failed; otherwise → repair.
    if escalation_issues:
        partial_artifact = state.get("draft_artifact")
        escalation_payload = build_escalation_report(
            stage_id="physical",
            report=report,
            partial_artifact=partial_artifact,
            attempt=state["attempt"],
        )
        return Command(
            goto="escalate",
            update={"evaluation_report": report, "escalation_report": escalation_payload},
        )
    if attempts_exhausted:
        return Command(
            goto=END,
            update={
                "evaluation_report": report,
                "error": {"message": "physical stage exceeded max attempts", "issues": report["issues"]},
            },
        )
    return Command(goto="repair", update={"evaluation_report": report})
```

(Add `escalation_report` to `PhysicalState` if not already present:

```python
class PhysicalState(TypedDict, total=False):
    # ... existing fields ...
    escalation_report: dict[str, Any] | None
```
)

- [ ] **Step 4: Mirror in `logical/nodes/validator.py`**

Same shape with `stage_id="logical"`. Add `escalation_report` to `LogicalState`.

- [ ] **Step 5: Add `escalate` node to stage graphs**

In `src/trace/stages/physical/__init__.py`:

```python
def _build_physical_graph(*, role_client, settings):
    del settings
    graph = StateGraph(PhysicalState)
    graph.add_node("prepare", prepare_node)
    graph.add_node("author", lambda state: author_node(state, role_client))
    graph.add_node("builder", lambda state: builder_node(state, role_client))
    graph.add_node("validator", validator_node)
    graph.add_node("repair", lambda state: repair_node(state, role_client))
    graph.add_node("finalize", finalize_node)
    graph.add_node("escalate", _escalate_node)
    graph.set_entry_point("prepare")
    graph.add_edge("prepare", "author")
    graph.add_edge("author", "builder")
    graph.add_edge("builder", "validator")
    graph.add_edge("repair", "validator")
    graph.add_edge("finalize", END)
    graph.add_edge("escalate", END)
    return graph.compile()


def _escalate_node(state: PhysicalState) -> dict[str, Any]:
    # Shape the final state so require_stage_result recognizes the escalated outcome.
    return {
        "result": {
            "status": "escalated",
            "escalation_report": state.get("escalation_report"),
            "partial_artifact": state.get("draft_artifact"),
            "evaluation_summary": state.get("evaluation_report"),
            "attempts_used": state.get("attempt", 1),
        },
        "events": [{"type": "physical.escalated", "attempt": state.get("attempt", 1)}],
    }
```

Mirror for logical stage.

- [ ] **Step 6: Update `require_stage_result` to recognize `escalated`**

In `src/trace/stages/common.py`, find `require_stage_result`. Adapt so that when `result["status"] == "escalated"`:

```python
def require_stage_result(*, stage_id: str, final_state: dict[str, Any]) -> dict[str, Any]:
    result = final_state.get("result")
    if not isinstance(result, dict):
        raise RuntimeError(f"{stage_id!r} stage produced no result")

    status = result.get("status")
    if status == "escalated":
        return {
            "status": "escalated",
            "escalation_report": result.get("escalation_report") or {},
            "partial_artifact": result.get("partial_artifact") or {},
            "evaluation_summary": result.get("evaluation_summary") or {},
            "attempts_used": result.get("attempts_used", 1),
            "messages": final_state.get("messages", []),
            "tool_journal": final_state.get("tool_journal", []),
            _stage_history_name(stage_id): final_state.get(_stage_history_name(stage_id), []),
            "events": final_state.get("events", []),
            "support_files": final_state.get("support_files", {}),
        }

    # ... existing handling for "completed" / "failed" ...
```

(Verify existing keys returned for non-escalated cases match the shape `TraceRuntime._merge_stage_result` consumes; preserve every key.)

- [ ] **Step 7: Run tests**

Run: `pytest tests/unit/stages/test_validator_escalation.py tests/unit/stages -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/trace/stages tests/unit/stages
git commit -m "feat(stages): validator routes escalation kinds to dedicated escalate node"
```

### Task 4.5: Wire `escalation_report` through `run_ground_stage` and `ground.author`

**Files:**
- Modify: `src/trace/stages/ground/__init__.py`
- Modify: `src/trace/stages/ground/nodes/author.py`
- Modify: `src/trace/stages/ground/nodes/evaluator.py` (unsolvable detection)
- Create test: `tests/unit/stages/test_ground_escalation_mode.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/stages/test_ground_escalation_mode.py
from langgraph.graph import END
from langgraph.types import Command


def test_author_node_includes_escalation_section_when_report_present(monkeypatch):
    from trace.stages.ground.nodes.author import author_node

    captured = {}

    def _stub_invoke_role(*, role_client, role_name, system_prompt_path, task, context_sections, schema):
        captured["task"] = task
        captured["context_sections"] = context_sections
        return [], {"intent": "x", "node_groups": [], "logical_constraints": [], "physical_constraints": []}

    monkeypatch.setattr("trace.stages.ground.nodes.author.invoke_role", _stub_invoke_role)
    state = {
        "intent": "x",
        "evaluation_report": None,
        "escalation_report": {
            "source_stage": "logical",
            "attempt_at_escalation": 2,
            "issues": [{"details": {"issue_kind": "logical.escalation.constraint_conflict", "summary": "A vs B"}}],
            "partial_artifact": {"graph": {"nodes": []}},
        },
    }
    author_node(state, role_client=None)
    assert "escalation_feedback" in captured["context_sections"]
    assert captured["context_sections"]["escalation_feedback"]["source_stage"] == "logical"
    assert "feedback_revision" in captured["task"] or "escalation" in captured["task"]


def test_evaluator_node_returns_unsolvable_command_when_artifact_flagged(monkeypatch):
    from trace.stages.ground.nodes.evaluator import evaluator_node

    def _stub_invoke_role(*, role_client, role_name, system_prompt_path, task, context_sections, schema):
        return [], {"passed": True, "issues": [], "notes": []}

    monkeypatch.setattr("trace.stages.ground.nodes.evaluator.invoke_role", _stub_invoke_role)
    state = {
        "draft_artifact": {
            "intent": "x",
            "node_groups": [],
            "logical_constraints": [],
            "physical_constraints": [],
            "unsolvable": True,
            "unsolvable_reason": "user intent contradicts itself",
        },
        "attempt": 1,
        "max_attempts": 3,
    }
    result = evaluator_node(state, role_client=None)
    assert isinstance(result, Command)
    assert result.goto == END
    assert result.update.get("status") == "unsolvable"
    assert "unsolvable_notes" in result.update
```

- [ ] **Step 2: Run tests to verify fail**

Run: `pytest tests/unit/stages/test_ground_escalation_mode.py -v`
Expected: FAIL — author_node ignores `escalation_report`; evaluator doesn't surface `unsolvable`.

- [ ] **Step 3: Update `run_ground_stage` signature**

In `src/trace/stages/ground/__init__.py`:

```python
def run_ground_stage(
    *,
    intent: str,
    role_client,
    settings: TraceSettings,
    escalation_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    graph = _build_ground_graph(role_client=role_client, settings=settings)
    with TemporaryDirectory(prefix="trace-ground-") as support_root:
        initial: GroundState = {
            "intent": intent,
            "attempt": 1,
            "max_attempts": settings.roles["ground_evaluator"].max_attempts,
            "status": "preparing",
            "retry_history": [],
            "events": [],
            "support_files": {},
            "support_file_root": support_root,
            "escalation_report": escalation_report,
        }
        final_state = graph.invoke(initial)
    return require_stage_result(stage_id="ground", final_state=final_state)
```

- [ ] **Step 4: Update `ground/nodes/author.py`**

Insert at the top of `author_node`, before computing `author_mode`:

```python
escalation_report = state.get("escalation_report")
escalation_mode = bool(escalation_report) and not _report_passed(state.get("evaluation_report"))
```

In the `revising` branch (or a new branch for escalation), inject:

```python
if escalation_mode:
    context_sections["escalation_feedback"] = escalation_report
    task = (
        "Current task mode: `feedback_revision` (escalation).\n"
        "A downstream stage reported issues that may stem from infeasible or conflicting constraints.\n"
        "Re-evaluate `node_groups`, `logical_constraints`, `physical_constraints` against `escalation_feedback.issues`.\n"
        "If the request is genuinely unsatisfiable, set `unsolvable=true` and fill `unsolvable_reason`.\n"
        "Otherwise return a revised complete `GroundDraftArtifact`."
    )
```

(Keep existing `feedback_revision` and `initial_draft` branches mutually exclusive: `escalation_mode` takes priority over `revising` when both are true.)

- [ ] **Step 5: Update `ground/nodes/evaluator.py`**

Convert to `Command` (Chunk 3 Task 3.7 already did this). Add an extra branch at the top of the post-evaluation logic:

```python
def evaluator_node(state: GroundState, role_client) -> Command:
    # ... existing semantic evaluation ...
    draft = state.get("draft_artifact", {})
    if draft.get("unsolvable"):
        reason = draft.get("unsolvable_reason") or "ground stage marked unsolvable"
        return Command(
            goto=END,
            update={
                "status": "unsolvable",
                "error": {"message": reason, "issues": draft.get("unsolvable_reason", [])},
                "unsolvable_notes": [reason],
                "events": [{"type": "ground.unsolvable", "reason": reason}],
            },
        )
    # ... existing pass/fail/retry routing ...
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/unit/stages/test_ground_escalation_mode.py tests/unit/stages -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/trace/stages/ground tests/unit/stages
git commit -m "feat(ground): author accepts escalation_report; evaluator surfaces unsolvable"
```

### Task 4.6: Engine routes escalated stage back to ground with counter cap

**Files:**
- Modify: `src/trace/runtime/engine.py`
- Create test: `tests/unit/runtime/test_escalation_routing.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/runtime/test_escalation_routing.py
from unittest.mock import MagicMock, patch
from trace.runtime.engine import TraceRuntime


def _runtime():
    settings = MagicMock()
    settings.roles = {}
    settings.langsmith.enabled = False
    return TraceRuntime(settings=settings, role_client=MagicMock(), output_root="runs/_tmp_escalation_test")


def test_logical_escalated_routes_back_to_ground():
    from langgraph.types import Command

    runtime = _runtime()
    state = {
        "run_id": "test", "intent": "x", "status": "running",
        "artifacts": {"ground": {"graph": {}}},
        "attempt_counters": {},
        "events": [], "support_files": {},
    }
    fake_result = {
        "status": "escalated",
        "escalation_report": {"source_stage": "logical", "issues": [{"details": {"issue_kind": "logical.escalation.constraint_conflict"}}]},
        "partial_artifact": {"graph": {}},
        "evaluation_summary": {"ok": False, "issues": []},
        "attempts_used": 2,
        "messages": [], "tool_journal": [], "repair_history": [], "events": [], "support_files": {},
    }
    with patch("trace.runtime.engine.run_logical_stage", return_value=fake_result):
        result = runtime._run_logical(state)
    assert isinstance(result, Command)
    assert result.goto == "ground"
    assert result.update["attempt_counters"]["escalation"] == 1
    assert len(result.update["escalation_history"]) == 1


def test_escalation_counter_cap_aborts_to_failed():
    from langgraph.graph import END
    from langgraph.types import Command

    runtime = _runtime()
    state = {
        "run_id": "test", "intent": "x", "status": "running",
        "artifacts": {"ground": {"graph": {}}},
        "attempt_counters": {"escalation": 2},  # cap reached
        "events": [], "support_files": {},
    }
    fake_result = {
        "status": "escalated",
        "escalation_report": {"source_stage": "physical"},
        "partial_artifact": {},
        "evaluation_summary": {"ok": False, "issues": []},
        "attempts_used": 1,
        "messages": [], "tool_journal": [], "repair_history": [], "events": [], "support_files": {},
    }
    with patch("trace.runtime.engine.run_physical_stage", return_value=fake_result):
        result = runtime._run_physical(state)
    assert isinstance(result, Command)
    assert result.goto == END
    assert result.update.get("status") == "failed"


def test_ground_consumes_escalation_report_once():
    runtime = _runtime()
    state = {
        "run_id": "test", "intent": "x", "status": "running",
        "artifacts": {}, "attempt_counters": {"escalation": 1},
        "events": [], "support_files": {},
        "escalation_report": {"source_stage": "logical", "issues": []},
    }
    fake_result = {
        "status": "completed",
        "artifact": {"intent": "x", "node_groups": [], "logical_constraints": [], "physical_constraints": []},
        "evaluation_summary": {"ok": True, "issues": []},
        "attempts_used": 1,
        "messages": [], "tool_journal": [], "retry_history": [], "events": [], "support_files": {},
    }
    captured_kwargs: dict = {}

    def _capture(**kwargs):
        captured_kwargs.update(kwargs)
        return fake_result

    with patch("trace.runtime.engine.run_ground_stage", side_effect=_capture):
        runtime._run_ground(state)
    assert "escalation_report" in captured_kwargs
    assert captured_kwargs["escalation_report"]["source_stage"] == "logical"
```

- [ ] **Step 2: Run tests to verify fail**

Run: `pytest tests/unit/runtime/test_escalation_routing.py -v`
Expected: FAIL — `_run_logical` etc. don't return `Command`; counter cap not enforced.

- [ ] **Step 3: Update engine `_run_*` methods**

Refactor `_run_logical` and `_run_physical` to return `Command` for the escalation case while still returning a plain dict (partial update) for the normal case (LangGraph accepts both). The cleanest pattern: always return `Command(goto=<next>, update=<partial>)` from the runtime nodes once one path needs `Command`.

```python
def _run_logical(self, state: RunState) -> Command | dict[str, Any]:
    try:
        with self.observer.stage_run("logical", run_id=state["run_id"]):
            result = run_logical_stage(
                ground_artifact=state["artifacts"]["ground"],
                inherited_support_files=state.get("support_files", {}),
                role_client=self.role_client,
                settings=self.settings,
            )
    except Exception as exc:  # noqa: BLE001
        return self._merge_stage_exception(state, "logical", exc)

    if result.get("status") == "escalated":
        return self._handle_stage_escalation(state, "logical", result)

    partial = self._merge_stage_result(state, "logical", result)
    return Command(goto="physical", update=partial)


def _run_physical(self, state: RunState) -> Command | dict[str, Any]:
    try:
        with self.observer.stage_run("physical", run_id=state["run_id"]):
            result = run_physical_stage(
                logical_artifact=state["artifacts"]["logical"],
                ground_artifact=state["artifacts"]["ground"],
                inherited_support_files=state.get("support_files", {}),
                role_client=self.role_client,
                settings=self.settings,
            )
    except Exception as exc:  # noqa: BLE001
        return self._merge_stage_exception(state, "physical", exc)

    if result.get("status") == "escalated":
        return self._handle_stage_escalation(state, "physical", result)

    partial = self._merge_stage_result(state, "physical", result)
    return Command(goto="finalize", update=partial)


def _run_ground(self, state: RunState) -> Command | dict[str, Any]:
    escalation_report = state.get("escalation_report")
    try:
        with self.observer.stage_run("ground", run_id=state["run_id"]):
            result = run_ground_stage(
                intent=state["intent"],
                role_client=self.role_client,
                settings=self.settings,
                escalation_report=escalation_report,
            )
    except Exception as exc:  # noqa: BLE001
        return self._merge_stage_exception(state, "ground", exc)

    partial = self._merge_stage_result(state, "ground", result)
    if escalation_report is not None:
        partial = {**partial, "escalation_report": None}  # consume once
    if result.get("status") == "unsolvable":
        partial["status"] = "unsolvable"
        return Command(goto=END, update=partial)
    return Command(goto="logical", update=partial)


ESCALATION_LIMIT = 2


def _handle_stage_escalation(self, state: RunState, stage_id: str, result: dict[str, Any]) -> Command:
    escalation_counter = (state.get("attempt_counters") or {}).get("escalation", 0)
    escalation_report = result.get("escalation_report") or {}
    payload = {
        "events": [{"type": f"{stage_id}.escalation_received", "stage": stage_id, "counter": escalation_counter + 1}],
        "escalation_history": [{
            "stage": stage_id,
            "counter": escalation_counter + 1,
            "report": escalation_report,
        }],
        "attempt_counters": {**(state.get("attempt_counters") or {}), "escalation": escalation_counter + 1},
    }
    if escalation_counter + 1 > ESCALATION_LIMIT:
        return Command(
            goto=END,
            update={
                **payload,
                "status": "failed",
                "error": {
                    "stage_id": stage_id,
                    "type": "EscalationLimitExceeded",
                    "message": f"escalation limit ({ESCALATION_LIMIT}) reached at {stage_id}",
                },
            },
        )
    return Command(
        goto="ground",
        update={
            **payload,
            "escalation_report": escalation_report,
            "current_stage": "ground",
        },
    )
```

- [ ] **Step 4: Drop `_next_unless_failed` conditional edges**

`Command(goto=...)` replaces conditional edges; in `_build_run_graph`:

```python
def _build_run_graph(self, *, entry_stage: str = "ground"):
    if entry_stage not in RUN_STAGE_ORDER:
        raise ValueError(f"unsupported run graph entry stage: {entry_stage}")
    graph = StateGraph(RunState)
    graph.add_node("ground", self._run_ground)
    graph.add_node("logical", self._run_logical)
    graph.add_node("physical", self._run_physical)
    graph.add_node("finalize", self._finalize)
    graph.set_entry_point(entry_stage)
    graph.add_edge("finalize", END)
    # Conditional routing is encoded in each node's Command return.
    return graph.compile()
```

`_merge_stage_exception` now also needs to return a `Command(goto=END, update=partial)` rather than a partial dict, to terminate the graph.

```python
def _merge_stage_exception(self, state: RunState, stage_id: str, exc: Exception) -> Command:
    # ... existing setup ...
    return Command(goto=END, update=partial)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/runtime/test_escalation_routing.py tests/integration/test_runtime_pipeline.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/trace/runtime/engine.py tests/unit/runtime/test_escalation_routing.py
git commit -m "feat(runtime): route escalated stage back to ground with counter cap"
```

### Task 4.7: Integration test for full escalation loop

**Files:**
- Create: `tests/integration/test_escalation_loop.py`

- [ ] **Step 1: Write integration test**

```python
# tests/integration/test_escalation_loop.py
import json
from pathlib import Path
from trace.runtime.engine import TraceRuntime


def test_full_escalation_loop_recovers(tmp_path, monkeypatch):
    """Simulate logical stage emitting an escalation issue on first call;
    ground revises artifact; second logical call succeeds.
    """
    runtime = TraceRuntime(output_root=tmp_path)

    call_count = {"ground": 0, "logical": 0, "physical": 0}

    def fake_ground(**kwargs):
        call_count["ground"] += 1
        return {
            "status": "completed",
            "artifact": {
                "intent": kwargs["intent"],
                "node_groups": [],
                "logical_constraints": [],
                "physical_constraints": [],
                "unsolvable": False,
            },
            "evaluation_summary": {"ok": True, "issues": []},
            "attempts_used": 1,
            "messages": [], "tool_journal": [], "retry_history": [],
            "events": [{"type": "ground.completed", "round": call_count["ground"]}],
            "support_files": {},
        }

    def fake_logical(**kwargs):
        call_count["logical"] += 1
        if call_count["logical"] == 1:
            return {
                "status": "escalated",
                "escalation_report": {
                    "source_stage": "logical",
                    "attempt_at_escalation": 1,
                    "issues": [{"details": {"issue_kind": "logical.escalation.constraint_conflict"}}],
                    "partial_artifact": {},
                },
                "partial_artifact": {"graph": {"nodes": [], "links": []}},
                "evaluation_summary": {"ok": False, "issues": []},
                "attempts_used": 1,
                "messages": [], "tool_journal": [], "repair_history": [], "events": [], "support_files": {},
            }
        return {
            "status": "completed",
            "artifact": {"graph": {"nodes": [{"id": "n1"}], "links": []}},
            "evaluation_summary": {"ok": True, "issues": []},
            "attempts_used": 1,
            "messages": [], "tool_journal": [], "repair_history": [], "events": [], "support_files": {},
        }

    def fake_physical(**kwargs):
        call_count["physical"] += 1
        return {
            "status": "completed",
            "artifact": {"graph": {"nodes": [], "links": []}, "constraint_files": {}, "checkpoint_files": {}},
            "evaluation_summary": {"ok": True, "issues": []},
            "attempts_used": 1,
            "messages": [], "tool_journal": [], "repair_history": [], "events": [], "support_files": {},
        }

    monkeypatch.setattr("trace.runtime.engine.run_ground_stage", fake_ground)
    monkeypatch.setattr("trace.runtime.engine.run_logical_stage", fake_logical)
    monkeypatch.setattr("trace.runtime.engine.run_physical_stage", fake_physical)

    final = runtime.run(intent="x", run_id="escalation-loop")

    assert call_count["ground"] == 2  # initial + revised
    assert call_count["logical"] == 2  # escalated + recovered
    assert call_count["physical"] == 1  # only after logical succeeds
    assert final["status"] == "completed"
    assert len(final.get("escalation_history", [])) == 1
    assert final["escalation_history"][0]["stage"] == "logical"


def test_escalation_limit_terminates(tmp_path, monkeypatch):
    runtime = TraceRuntime(output_root=tmp_path)

    def fake_ground(**kwargs):
        return {
            "status": "completed",
            "artifact": {"intent": "x", "node_groups": [], "logical_constraints": [], "physical_constraints": []},
            "evaluation_summary": {"ok": True, "issues": []},
            "attempts_used": 1,
            "messages": [], "tool_journal": [], "retry_history": [], "events": [], "support_files": {},
        }

    def fake_logical(**kwargs):
        return {
            "status": "escalated",
            "escalation_report": {"source_stage": "logical", "issues": []},
            "partial_artifact": {},
            "evaluation_summary": {"ok": False, "issues": []},
            "attempts_used": 1,
            "messages": [], "tool_journal": [], "repair_history": [], "events": [], "support_files": {},
        }

    monkeypatch.setattr("trace.runtime.engine.run_ground_stage", fake_ground)
    monkeypatch.setattr("trace.runtime.engine.run_logical_stage", fake_logical)

    final = runtime.run(intent="x", run_id="escalation-cap")
    assert final["status"] == "failed"
    assert "EscalationLimitExceeded" in final.get("error", {}).get("type", "")
```

- [ ] **Step 2: Run test**

Run: `pytest tests/integration/test_escalation_loop.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_escalation_loop.py
git commit -m "test(integration): end-to-end escalation loop and counter cap"
```

### Task 4.8: Wire SqliteSaver into `_build_run_graph` and `graph.invoke`

**Files:**
- Modify: `src/trace/runtime/engine.py`
- Create test: `tests/unit/runtime/test_checkpointer.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/runtime/test_checkpointer.py
from pathlib import Path
from unittest.mock import patch
from trace.runtime.engine import TraceRuntime


def test_state_sqlite_created_after_run(tmp_path, monkeypatch):
    runtime = TraceRuntime(output_root=tmp_path)

    def _stub(**kwargs):
        return {
            "status": "completed",
            "artifact": {"intent": "x", "node_groups": [], "logical_constraints": [], "physical_constraints": []},
            "evaluation_summary": {"ok": True, "issues": []},
            "attempts_used": 1,
            "messages": [], "tool_journal": [], "retry_history": [], "repair_history": [], "events": [], "support_files": {},
        }

    monkeypatch.setattr("trace.runtime.engine.run_ground_stage", _stub)
    monkeypatch.setattr("trace.runtime.engine.run_logical_stage", _stub)
    monkeypatch.setattr("trace.runtime.engine.run_physical_stage", _stub)

    runtime.run(intent="x", run_id="ckpt-001")
    assert (tmp_path / "ckpt-001" / "state.sqlite").exists()


def test_resume_picks_up_from_sqlite_when_present(tmp_path, monkeypatch):
    # Build a complete run with sqlite present, then resume from logical.
    runtime = TraceRuntime(output_root=tmp_path)

    def _ground(**kwargs):
        return {
            "status": "completed",
            "artifact": {"intent": "x", "node_groups": [], "logical_constraints": [], "physical_constraints": []},
            "evaluation_summary": {"ok": True, "issues": []},
            "attempts_used": 1,
            "messages": [], "tool_journal": [], "retry_history": [], "events": [], "support_files": {},
        }

    monkeypatch.setattr("trace.runtime.engine.run_ground_stage", _ground)
    # Make logical fail so resume has work to do
    def _logical_fail(**kwargs):
        raise RuntimeError("synthetic failure for resume test")

    monkeypatch.setattr("trace.runtime.engine.run_logical_stage", _logical_fail)
    runtime.run(intent="x", run_id="resume-base")

    sqlite_path = tmp_path / "resume-base" / "state.sqlite"
    assert sqlite_path.exists(), "sqlite must exist after a failed run for resume to use it"
```

- [ ] **Step 2: Run tests to verify fail**

Run: `pytest tests/unit/runtime/test_checkpointer.py -v`
Expected: FAIL.

- [ ] **Step 3: Wire SqliteSaver**

In `src/trace/runtime/engine.py`:

```python
from langgraph.checkpoint.sqlite import SqliteSaver


class TraceRuntime:
    # ... existing __init__ ...

    def _checkpointer_for(self, run_id: str) -> SqliteSaver:
        run_root = self.storage.root / run_id
        run_root.mkdir(parents=True, exist_ok=True)
        sqlite_path = run_root / "state.sqlite"
        return SqliteSaver.from_conn_string(str(sqlite_path))

    def _build_run_graph(self, *, entry_stage: str = "ground", checkpointer: SqliteSaver | None = None):
        if entry_stage not in RUN_STAGE_ORDER:
            raise ValueError(f"unsupported run graph entry stage: {entry_stage}")
        graph = StateGraph(RunState)
        graph.add_node("ground", self._run_ground)
        graph.add_node("logical", self._run_logical)
        graph.add_node("physical", self._run_physical)
        graph.add_node("finalize", self._finalize)
        graph.set_entry_point(entry_stage)
        graph.add_edge("finalize", END)
        return graph.compile(checkpointer=checkpointer)

    def run(self, intent: str, run_id: str | None = None) -> dict[str, Any]:
        resolved_run_id = run_id or uuid4().hex[:8]
        initial: RunState = {
            "run_id": resolved_run_id,
            "intent": intent,
            "status": "running",
            "current_stage": "ground",
            "artifacts": {},
            "stage_reports": {},
            "attempt_counters": {},
            "support_files": {},
            "events": [{"type": "run.started"}],
            "escalation_history": [],
            "error": None,
            "config_snapshot": self._config_snapshot(),
        }
        self.storage.initialize_run(run_id=resolved_run_id, run_payload=initial)
        with self._checkpointer_for(resolved_run_id) as checkpointer:
            with self.observer.root_run(run_id=resolved_run_id, intent=intent):
                graph = self._build_run_graph(checkpointer=checkpointer)
                final_state = graph.invoke(
                    initial,
                    config={"configurable": {"thread_id": resolved_run_id}},
                )
        self.storage.write_run_state(run_id=resolved_run_id, run_payload=final_state)
        self.storage.append_run_events(run_id=resolved_run_id, events=final_state.get("events", []))
        return final_state
```

(Note: `SqliteSaver.from_conn_string(...)` is a context manager in current versions; wrap the run in `with ... as checkpointer:`. Verify against the installed version.)

- [ ] **Step 4: Update `resume(...)` to prefer sqlite**

In `resume(...)`:

```python
def resume(
    self,
    run_id: str,
    *,
    from_stage: str,
    new_run_id: str | None = None,
    in_place: bool = False,
) -> dict[str, Any]:
    resume_stage = _normalize_resume_stage(from_stage)
    if in_place and new_run_id is not None:
        raise ValueError("new_run_id cannot be used with in_place resume")
    sqlite_path = self.storage.root / run_id / "state.sqlite"

    target_run_id = run_id if in_place else new_run_id or self._next_resume_run_id(run_id, resume_stage)
    if not in_place and target_run_id == run_id:
        raise ValueError("new_run_id must differ from source run_id unless in_place=True")

    sqlite_usable = in_place and sqlite_path.exists()

    if sqlite_usable:
        return self._resume_via_sqlite(
            source_run_id=run_id,
            target_run_id=target_run_id,
            resume_stage=resume_stage,
        )
    return self._resume_via_run_storage(
        source_run_id=run_id,
        target_run_id=target_run_id,
        resume_stage=resume_stage,
        in_place=in_place,
    )


def _resume_via_sqlite(self, *, source_run_id: str, target_run_id: str, resume_stage: str) -> dict[str, Any]:
    source_state = self.storage.read_run_state(source_run_id)
    intent = str(source_state.get("intent") or "")
    with self._checkpointer_for(target_run_id) as checkpointer:
        graph = self._build_run_graph(entry_stage=resume_stage, checkpointer=checkpointer)
        with self.observer.root_run(run_id=target_run_id, intent=intent):
            history = list(graph.get_state_history({"configurable": {"thread_id": source_run_id}}))
            target_checkpoint = None
            for snapshot in history:
                state_dict = snapshot.values if isinstance(snapshot.values, dict) else {}
                if state_dict.get("current_stage") == resume_stage:
                    target_checkpoint = snapshot
                    break
            if target_checkpoint is None:
                raise ValueError(
                    f"sqlite checkpoint for stage {resume_stage!r} not found in {source_run_id!r}"
                )
            final_state = graph.invoke(
                None,
                config={"configurable": {"thread_id": source_run_id, "checkpoint_id": target_checkpoint.config["configurable"].get("checkpoint_id")}},
            )
    self.storage.write_run_state(run_id=target_run_id, run_payload=final_state)
    return final_state


def _resume_via_run_storage(self, *, source_run_id: str, target_run_id: str, resume_stage: str, in_place: bool) -> dict[str, Any]:
    # ... existing logic moved here verbatim, wrapped with _checkpointer_for(target_run_id) so the new run still gets a fresh sqlite ...
    source_state = self.storage.read_run_state(source_run_id)
    reused_stages = list(REQUIRED_RESUME_ARTIFACTS[resume_stage])
    artifacts = self._load_resume_artifacts(source_run_id=source_run_id, from_stage=resume_stage)
    intent = str(source_state.get("intent") or "")
    initial = {
        "run_id": target_run_id,
        "intent": intent,
        "status": "running",
        "current_stage": resume_stage,
        "artifacts": artifacts,
        "stage_reports": {},
        "attempt_counters": {},
        "support_files": self._load_resume_support_files(source_run_id=source_run_id, from_stage=resume_stage),
        "events": [{"type": "run.resumed", "source_run_id": source_run_id, "from_stage": resume_stage, "target_run_id": target_run_id, "reused_stages": reused_stages}],
        "escalation_history": [],
        "error": None,
        "config_snapshot": self._config_snapshot(),
        "resume": {"source_run_id": source_run_id, "from_stage": resume_stage, "reused_stages": reused_stages},
    }
    self.storage.initialize_run(run_id=target_run_id, run_payload=initial)
    if not in_place:
        for stage_id in reused_stages:
            self.storage.copy_stage_snapshot(source_run_id=source_run_id, target_run_id=target_run_id, stage_id=stage_id)
    with self._checkpointer_for(target_run_id) as checkpointer:
        with self.observer.root_run(run_id=target_run_id, intent=intent):
            graph = self._build_run_graph(entry_stage=resume_stage, checkpointer=checkpointer)
            final_state = graph.invoke(initial, config={"configurable": {"thread_id": target_run_id}})
    self.storage.write_run_state(run_id=target_run_id, run_payload=final_state)
    self.storage.append_run_events(run_id=target_run_id, events=final_state.get("events", []))
    return final_state
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/runtime/test_checkpointer.py tests/integration/test_runtime_pipeline.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/trace/runtime/engine.py tests/unit/runtime/test_checkpointer.py
git commit -m "feat(runtime): wire SqliteSaver checkpointer with RunStorage dual-track resume"
```

### Task 4.9: README + docs update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Locate the "从阶段恢复" section**

Run: `rg -n "从阶段恢复|resume|Resume" README.md`
Capture surrounding context.

- [ ] **Step 2: Append the SqliteSaver + escalation paragraph**

After the existing resume description, add:

```markdown
### 状态持久化与恢复策略

每次 `trace run` 会在 `runs/<run_id>/state.sqlite` 落地一份 LangGraph 状态 (Checkpointer)；
`runs/<run_id>/run.json` 与 `<stage>/` 子目录仍作为人类可读快照保留。

恢复时：
- `--in-place` 模式下，如果 sqlite 存在则从最近的 stage checkpoint 继续（包括中间未完成的 attempt）；
- `--new-run-id <id>` 模式（默认）下，始终走 `RunStorage` 路径：把上一 run 的 stage 快照拷贝进新 `runs/<new_id>/` 目录后重新跑，并在新目录里建立自己的 sqlite。

### Escalation 反馈通道

logical / physical stage 在遇到 `*.escalation.*` 类 issue 时不会进入 repair，而是把
`escalation_report` 回流给 ground，由 ground 重新评估 constraints。计数器
`attempt_counters.escalation` 上限为 2 次；超出则整体失败。
若 ground 判断 `unsolvable=true`，run 直接以 `status="unsolvable"` 终止并提示用户检查 intent。
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: describe SqliteSaver resume and escalation channel"
```

### Task 4.10: Final verification + demo smoke

- [ ] **Step 1: Full unit + integration suite**

Run: `pytest -q`
Expected: all green.

- [ ] **Step 2: Two demo smokes**

```powershell
$env:LANGSMITH_TRACING="false"
trace run tests/demo/demo.md --run-id pr4-smoke-001 --output-root runs
```

Expected:
- Run completes.
- `runs/pr4-smoke-001/state.sqlite` exists.
- `runs/pr4-smoke-001/run.json` contains `escalation_history: []` (since this demo doesn't escalate).
- `runs/pr4-smoke-001/events.jsonl` contains a `run.completed` entry.

Then resume:

```powershell
trace resume pr4-smoke-001 --from physical --in-place
```

Expected: resume picks up from sqlite (logs say "sqlite checkpoint found") and re-runs physical.

- [ ] **Step 3: Synthesized escalation smoke**

Author a minimal `tests/demo/escalation_demo.md` whose `intent` deliberately conflicts (e.g., "Build a network with two firewalls but no firewall capable image in catalog"), then:

```powershell
trace run tests/demo/escalation_demo.md --run-id pr4-esc-001 --output-root runs
```

Expected: `runs/pr4-esc-001/run.json` shows non-empty `escalation_history`; final `status` is either `completed` (ground revised successfully) or `unsolvable` (ground gave up).

- [ ] **Step 4: Branch / PR**

Open PR titled `feat: PR4 SqliteSaver checkpointer + ground escalation reverse channel`. Reference spec modules C3 + G. List the eight original problems and which PR addressed each in the PR description.

PR4 chunk done.

---

## Plan finalization

All four chunks (PR1 / PR2 / PR3 / PR4) are now in this document. Execution order is strict — PR2 builds on PR1's ledger shape; PR3 builds on PR2's reducer-style ledger writes (the Chunk 2 tasks intentionally land manual `[*prior, entry]` patterns that PR3 strips); PR4 builds on PR3's `Command` routing and `escalation_history` field. Do not interleave.

Run order after each chunk lands on the feature branch:

1. `pytest -q` — entire suite green.
2. Demo smoke (PowerShell shown):

   ```powershell
   $env:LANGSMITH_TRACING="false"
   trace run tests/demo/demo.md --run-id chunk-N-smoke --output-root runs
   ```

3. Open PR. Reference the spec module(s) covered by the chunk in the PR body and link this plan file.

Reviewer guidance per chunk:

- **PR1** — focus on prompt diff and tool surface; verify no API-listing leakage in `src/trace/stages/*/prompts`.
- **PR2** — focus on `_derive_produced_files` correctness (especially mutation/execute pairing edge cases enumerated in spec NI-2) and `diff` view semantics.
- **PR3** — focus on reducer behavior across nodes; check that no node still does `[*prev, ...]`; verify `Command.goto` covers every previous `next_action` value.
- **PR4** — focus on (a) sqlite-aware resume path correctness and (b) escalation counter precedence; check `_handle_stage_escalation` for off-by-one on the cap.

Plan complete.
