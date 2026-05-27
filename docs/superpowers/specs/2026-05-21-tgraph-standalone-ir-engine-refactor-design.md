# TGraph Standalone IR Engine Refactor Design

## Goal

Refactor TGraph into a standalone IaC IR engine that can be used by TRACE, Codex Skills, Claude Code instructions, LangGraph applications, CLIs, and future tools without inheriting TRACE's workflow, knowledge base, image catalog, or LangGraph runtime.

TGraph should provide the stable substrate:

- A graph-based IaC intermediate representation.
- Focused graph operations.
- Automatic validation with an F1-F4 model.
- Input and output boundaries for TGraph documents.
- Placeholder target interfaces for future IaC emitters.
- Agent-facing protocols and CLI wrappers.

TRACE remains the agentic application layer. TRACE owns natural-language intent handling, ground/logical/physical workflow orchestration, image catalogs, domain knowledge, repair policy, and LangGraph state.

## Core Boundary

TGraph is not an IaC agent and not a workflow engine.

TGraph owns:

- IR model and document compatibility.
- Canonical graph representation.
- Read-only inspection.
- Declarative batch patching.
- Validation.
- TGraph document IO.
- Target emitter interfaces.
- Agent operation contracts.

TGraph does not own:

- Natural-language understanding.
- Ground artifact authoring.
- LangGraph orchestration.
- Codex or Claude Code decision loops.
- Image, flavor, or module catalogs.
- Domain pattern libraries.
- Terraform, Pulumi, or TOSCA implementation in the first phase.
- Provider selection or deployment policy.

This keeps TGraph stable while allowing different outer systems to use it in different ways.

```text
TRACE / Skill / LangGraph / other app
  owns workflow, knowledge, catalogs, policy, LLM calls
  calls into:

tgraph
  owns IR, operations, validation, IO, target contracts
```

## Design Principles

1. Keep the public surface small.

   Agents do better with a few strong tools than with many low-level CRUD tools. Public mutation should be batch patch based.

2. Treat TGraph as one IR.

   Logical and physical graphs should not be separate object models. They are the same TGraph structure at different maturity stages.

3. Keep the document header minimal.

   Phase one should keep only the fields that are needed for the IR to work. `stage` describes maturity such as `logical` or `physical`. `schema_version`, `profile`, and top-level `metadata` are intentionally deferred until there is a concrete compatibility or extension requirement.

4. Validate in layers.

   Preserve the F1-F4 idea, but define it around clean input boundaries:

   - F1: raw document format.
   - F2: IR schema.
   - F3: graph consistency.
   - F4: intent/context constraints supplied by the caller.

5. Keep workflow outside the SDK.

   LangGraph, Codex, Claude Code, or another application decides what to do next. TGraph returns machine-readable results that make that decision easier.

6. Keep knowledge outside the SDK.

   Image catalogs, network scenario libraries, provider modules, and domain policy are caller-owned inputs. TGraph may validate references supplied to it, but it should not ship or manage those catalogs in phase one.

7. Design for agent repair loops.

   Every operation should return stable JSON, issue codes, diffs, and enough context for an agent to make a next patch without reading the whole graph repeatedly.

## Package Shape

Phase one introduces a standalone `tgraph` package. It may live in the same repository initially, but it must have a clean import boundary. The package and import namespace should not include `trace`; TRACE is only one application that consumes TGraph.

```text
tgraph/
  core/
  operations/
  io/
  targets/
  agent/
  cli/
```

Existing TRACE code may keep compatibility wrappers during migration, but new TGraph logic should live under `tgraph`.

## Module Design

### `core`

`core` answers: what is a TGraph and how is it represented canonically?

```text
tgraph/core/
  graph.py       # TGraph, Node, Port, Link, ImageSpec, FlavorSpec
  stage.py       # graph maturity marker
  schema.py      # Pydantic schemas and structural type constraints
  normalize.py   # canonical representation
  errors.py      # core parse and normalization errors
```

The canonical document shape should be explicit:

```json
{
  "stage": "logical",
  "nodes": [],
  "links": []
}
```

`stage` is a validation and maturity marker. It does not switch the object model.

Top-level `metadata` is intentionally absent in phase one. Caller-specific annotations, provenance, workflow notes, catalog choices, and domain knowledge should live in the outer application envelope until TGraph has a well-defined extension policy.

Built-in stages for phase one:

- `logical`: topology and intent-level graph. Physical deployment fields may be missing.
- `physical`: topology plus deployment-oriented fields. Required physical fields depend on caller policy and target readiness.

Future applications may add stricter policies, but the base IR should remain the same.

`normalize.py` exists to make equivalent graphs stable. It handles canonical link IDs, endpoint ordering, stable node/link ordering, default empty-field cleanup, and deterministic serialization support. This is necessary for patch diffs, snapshot tests, artifact comparison, and reproducible agent workflows.

### `operations`

`operations` answers: what can be done to an existing TGraph?

```text
tgraph/operations/
  inspect/
  patch/
  validate/
```

#### `operations.inspect`

Read-only graph views. These are agent and UI friendly, and they prevent callers from repeatedly loading or printing whole graphs.

```text
operations/inspect/
  summary.py     # graph summary and topology overview
  nodes.py       # node lookup and filtering
  ports.py       # port lookup and usage
  links.py       # link lookup and adjacency
  paths.py       # reachability and path queries
  segments.py    # subnet or segment-oriented views when derivable
```

Inspection must not mutate or validate by side effect.

#### `operations.patch`

The only public mutation model.

```text
operations/patch/
  schema.py      # patch envelope and operation schemas
  apply.py       # atomic candidate application
  diff.py        # before/after graph diff
  result.py      # PatchResult model
  errors.py      # stable patch errors
```

Patch application should follow this lifecycle:

```text
input graph
  -> copy candidate
  -> apply all operations
  -> normalize candidate
  -> optionally validate candidate
  -> return result with diff and issues
```

Phase one public graph operations:

- `ensure_node`
- `ensure_port`
- `ensure_link`
- `remove_node`
- `remove_port`
- `remove_link`
- `set_stage`

Operations should be idempotent when possible. Destructive operations must be explicit. Long-lived transaction handles are not part of the public model.

The patch result should include:

- `ok`
- `committed` or `would_commit`
- accepted and rejected operation details
- stable error codes
- diff summary
- optional candidate artifact
- optional validation report

#### `operations.validate`

Validation owns the F1-F4 model.

```text
operations/validate/
  runner.py      # validate_document and validate_graph
  policy.py      # stage-aware validation policy
  issues.py      # ValidationIssue and ValidationReport
  f1_format.py
  f2_schema.py
  f3_graph.py
  f4_intent.py
```

Two public entrypoints are required:

```python
validate_document(raw: dict, policy: ValidationPolicy) -> ValidationReport
validate_graph(graph: TGraph, policy: ValidationPolicy, context: ValidationContext | None = None) -> ValidationReport
```

Layer semantics:

- F1 validates raw document shape and basic JSON compatibility.
- F2 parses and validates the TGraph IR schema.
- F3 validates graph consistency: endpoint references, canonical links, port degree, node/link uniqueness, and address consistency.
- F4 validates caller-provided intent and context constraints, such as checkpoints or preservation requirements.

F4 should not fetch image catalogs or domain knowledge. Those are external inputs. F4 may validate against constraints supplied by TRACE, a Skill, or another caller.

### `io`

`io` answers: how does TGraph enter and leave the SDK as a document?

```text
tgraph/io/
  json.py        # load and dump TGraph JSON
  document.py    # document envelope compatibility
  importers/     # future external topology importers
  exporters/     # TGraph document exporters, not IaC emitters
```

`io` is not responsible for Terraform or Pulumi generation. It only handles graph document formats and import/export of graph data.

Phase one IO should support:

- Load raw JSON or dict into a normalized TGraph.
- Dump a TGraph to stable JSON.
- Validate before or after loading.
- Reject unknown top-level fields unless the IO layer explicitly supports them.
- Provide clear document-shape and compatibility errors.

Future IO importers may include GNS3, GML, or other topology formats. Those importers should produce TGraph documents, not target IaC.

### `targets`

`targets` answers: what is the contract for generating external IaC outputs?

Phase one only defines the interface and registry. It does not implement Terraform, Pulumi, or TOSCA generation.

```text
tgraph/targets/
  base.py        # TargetEmitter protocol
  registry.py    # target lookup
  result.py      # EmitResult and output bundle model
  terraform.py   # placeholder emitter
  pulumi.py      # placeholder emitter
  tosca.py       # placeholder emitter
```

The target contract should be explicit:

```python
class TargetEmitter(Protocol):
    name: str

    def emit(self, graph: TGraph, options: EmitOptions) -> EmitResult:
        ...
```

Placeholder emitters return a stable `target_not_implemented` error. This lets Agent and CLI workflows stabilize before backend-specific code generation is designed.

`tgraph-json` is not a target. It belongs in `io`.

### `agent`

`agent` answers: how should Codex, Claude Code, and similar agents use TGraph safely?

```text
tgraph/agent/
  protocol.py
  schemas/
    tgraph.schema.json
    patch.schema.json
    validation-report.schema.json
    inspect-result.schema.json
  playbooks/
    repair.md
    authoring.md
    validation.md
    emission.md
  examples/
```

Agent docs are adapters over the SDK facts, not a second source of truth. They should describe:

- When to inspect before patching.
- How to form one coherent patch.
- How to interpret validation issues.
- How to iterate after rejected operations.
- How to avoid inventing knowledge or image choices that the caller did not provide.

The agent layer contains protocol and guidance only. It must not contain TRACE workflow logic.

### `cli`

`cli` answers: how do humans and agents call the SDK from a shell?

```text
tgraph/cli/
  main.py
```

Phase one commands:

```bash
tgraph inspect graph.json --view topology --json
tgraph validate graph.json --stage logical --levels f1,f2,f3,f4 --json
tgraph patch graph.json patch.json --out graph.json --json
tgraph normalize graph.json --out graph.json
tgraph import json graph.json --out graph.json
tgraph export json graph.json --out graph.json
tgraph emit terraform graph.json --out ./iac --json
```

`emit terraform` exists only to exercise the target interface and should return `target_not_implemented` until the Terraform backend is designed.

All CLI commands must return stable JSON when `--json` is supplied. Errors should be machine-readable and should not expose raw Python tracebacks by default.

## Public API Sketch

The top-level API should be small:

```python
from tgraph import (
    TGraph,
    load_tgraph,
    dump_tgraph,
    normalize_graph,
    inspect_graph,
    apply_patch,
    validate_document,
    validate_graph,
    emit_target,
)
```

The agent-facing mental model should be even smaller:

```text
inspect -> patch -> validate -> repeat -> emit
```

The outer application decides what the graph means and what to do next.

## TRACE Application Boundary

TRACE should consume `tgraph` instead of owning TGraph internals.

TRACE continues to own:

- Ground artifact extraction.
- Logical and physical stage orchestration.
- LangGraph node state.
- LLM calls.
- Image and flavor catalog queries.
- Domain knowledge and pattern selection.
- Repair retry policy.
- Artifact storage and observability.

TRACE calls TGraph for:

- Loading and normalizing TGraph documents.
- Inspecting graph state.
- Applying batch patches.
- Running F1-F4 validation.
- Emitting target outputs once target backends exist.

This boundary lets TRACE change its workflow without changing the TGraph SDK, and lets non-TRACE users adopt the SDK without importing TRACE.

## Validation Context

F4 validation needs caller-supplied context, but that context should stay data-shaped and explicit.

Examples:

```json
{
  "stage": "logical",
  "checkpoints": [],
  "preserve_topology_from": null,
  "required_node_fields": [],
  "required_link_fields": []
}
```

The SDK validates against this context. It does not go look up knowledge or decide which image should satisfy a SCADA role.

If TRACE wants to check image catalog compatibility, TRACE first queries its catalog and then passes explicit requirements or constraints into TGraph validation.

## Error Model

All public operations should return stable errors.

Recommended error families:

- `document_error`
- `schema_error`
- `normalization_error`
- `patch_schema_error`
- `patch_conflict`
- `validation_failed`
- `target_not_implemented`
- `target_error`
- `io_error`

Every error should include:

- `code`
- `message`
- optional `location`
- optional `details`
- optional `suggested_next_action`

Agent-facing errors should be concise and actionable.

## Migration Plan

Phase one is a refactor with compatibility, not a flag-day rewrite.

1. Add `tgraph` package boundary.

   Start with core IR models, normalization, validation models, patch schemas, and IO helpers. Keep behavior close enough to current TGraph artifacts to avoid breaking TRACE.

2. Add compatibility adapters.

   Existing `trace.tools.tgraph` imports can re-export or delegate to `tgraph` while TRACE callers migrate.

3. Move validation orchestration.

   Create a single validation runner in `tgraph.operations.validate`. Existing validators may be adapted, but the new runner owns the public contract.

4. Move patch application.

   Make batch patch the public mutation API. Existing transaction and CRUD tool layers become compatibility wrappers or are deprecated.

5. Add IO and CLI.

   Provide stable load, dump, normalize, inspect, validate, patch, and placeholder emit commands.

6. Add agent protocols.

   Publish schemas, playbooks, examples, and issue-code references for Codex and Claude Code style agents.

7. Update TRACE to consume `tgraph`.

   TRACE retains its workflows and knowledge integrations, but uses the standalone SDK for IR operations.

8. Remove old public mutation paths after migration.

   Delete or privatize `transaction.py` and low-level CRUD agent tools only after all callers have moved to batch patch.

## Testing Strategy

Core tests:

- TGraph parse and dump round trips.
- Stage marker stays stable.
- Normalization is deterministic and idempotent.
- Invalid documents fail with stable error codes.

Operation tests:

- Inspect views for nodes, links, ports, paths, and topology summaries.
- Patch idempotency for `ensure_*` operations.
- Patch conflict handling.
- Destructive patch behavior.
- Diff generation.
- Validation-gated patch application.

Validation tests:

- F1 raw document failures.
- F2 schema failures.
- F3 graph consistency failures.
- F4 caller context failures.
- Stage-aware validation policies.

CLI tests:

- Commands emit stable JSON.
- Errors avoid raw tracebacks.
- `emit terraform` returns `target_not_implemented`.
- Running from arbitrary working directories works.

Agent protocol tests:

- JSON schemas validate examples.
- Playbook examples map to valid CLI commands.
- A minimal repair loop can inspect, patch, validate, and stop on success.

TRACE compatibility tests:

- Existing logical and physical artifacts still load.
- Current TRACE stage tests can use compatibility adapters.
- Existing TGraph validation behavior is preserved where intentionally retained.

## Non-Goals For Phase One

- Real Terraform, Pulumi, or TOSCA generation.
- Built-in domain knowledge.
- Built-in image, flavor, or module catalogs.
- Built-in network scenario pattern libraries.
- Natural-language intent handling.
- LangGraph workflow orchestration.
- Full redesign of TRACE stages.
- Public long-lived transactions.
- Public low-level CRUD mutation tools.

## Open Follow-Up Designs

These should be designed separately after the standalone IR engine is stable:

- Terraform backend emitter contract and implementation.
- Pulumi backend emitter contract and implementation.
- TRACE knowledge and image catalog architecture.
- TRACE LangGraph migration to `tgraph`.
- Codex/Claude Code Skill packaging around the new CLI.
- Declarative F4 checkpoint language.
