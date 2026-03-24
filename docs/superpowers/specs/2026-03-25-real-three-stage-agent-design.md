# TRACE Real Three-Stage Agent Design

Date: 2026-03-25
Status: Draft approved in conversation, written for review
Scope: replace default fake fixtures with real `ground -> logical -> physical` agent execution

## 1. Summary

This document defines the next-step TRACE runtime design for replacing the default fake fixtures with real three-stage agent execution.

The core design decision is to keep stage final artifacts graph-centric while making agent round outputs patch-centric.

That means:

- `ground` still outputs node declarations and natural-language constraints
- `logical` still ends with an authoritative `tgraph_logical`
- `physical` still ends with an authoritative `tgraph_physical`
- but `logical` and `physical` no longer need to regenerate full graphs every round
- runtime owns the authoritative graph state and applies patch plans between rounds

This design is intended to support larger topologies, reduce token usage, reduce graph-regeneration noise, and make repair loops more stable.

## 2. Goals

### 2.1 In scope

- Replace fake default stage fixtures with real three-stage agent execution
- Keep the stage order as `ground -> logical -> physical -> translate_stub`
- Let `ground` transform abstract user intent into executable natural-language constraints
- Freeze all available node IDs in `ground`
- Support compact node declarations such as `PLC[1..100]`
- Support compact node references inside natural-language constraints such as `PLC[1..6]`
- Keep constraints expert-readable as natural language rather than introducing a heavy DSL
- Use runtime-controlled outer repair loops for `logical` and `physical`
- Make `logical` and `physical` patch-first for graph construction and repair
- Allow `logical` and `physical` to revise their own checkpoints and validator scripts during repair
- Preserve stage boundaries so `physical` cannot silently rewrite logical connectivity

### 2.2 Out of scope

- Real translation after `physical`
- Automatic cross-stage rollback in v1
- Replacing natural-language constraints with a full formal constraint language
- Letting `physical` redesign the logical topology
- Long-lived graph memory inside the model

## 3. Options Considered

### 3.1 Full-graph every round

Each stage agent always returns a complete graph on every round.

Pros:

- simplest runtime
- easiest to reason about in small examples

Cons:

- poor fit for large topologies
- expensive in tokens and latency
- high risk of introducing fresh errors while fixing old ones

### 3.2 First round full graph, later rounds patch

The initial graph is returned in full, then later rounds switch to patch repair.

Pros:

- simpler migration path from the current runtime
- cheaper repair rounds

Cons:

- still expensive on large initial builds
- still exposes first-round graph generation to avoidable churn

### 3.3 Patch-first runtime-owned graphs

The agent returns checkpoints, scripts, and patch plans; runtime owns authoritative graph assembly.

Pros:

- best fit for large topologies
- lowest token cost over time
- fastest repair loop
- clearest stage boundaries

Cons:

- requires the largest runtime redesign
- requires richer patch semantics

### 3.4 Recommendation

Use option 3.

TRACE should treat runtime as the graph state machine and treat stage agents as patch planners plus constraint/checkpoint authors.

## 4. End-to-End Flow

The workflow remains:

`ground -> logical -> physical -> translate_stub`

The behavioral difference is:

- `ground` returns final stage artifacts directly
- `logical` and `physical` return round outputs
- runtime transforms those round outputs into final stage artifacts

High-level data flow:

1. `ground` reads user intent and produces node declarations plus natural-language constraints
2. runtime expands node patterns into frozen node IDs
3. `logical` authors checkpoints and a validator script
4. runtime creates a logical skeleton graph from frozen node IDs
5. `logical` returns patch plans to build and repair the logical graph
6. runtime applies patches and persists `tgraph_logical`
7. `physical` authors checkpoints and a validator script using physical constraints plus logical outputs
8. runtime creates a physical skeleton graph from `tgraph_logical`
9. `physical` returns patch plans to build and repair the physical graph
10. runtime applies patches and persists `tgraph_physical`

## 5. Ground Stage

### 5.1 Responsibility

`ground` is not a mere intent restatement stage.

It should use model knowledge and domain knowledge to convert abstract user goals into executable constraints.

For example, a request such as:

`构建一个典型的工业控制网络，20个节点左右，需要用到施耐德M580 PLC`

should not remain at the level of raw user wording. `ground` should infer and encode missing but necessary structure such as:

- layered industrial network expectations
- segmentation expectations
- trunk or backbone organization expectations
- control and management isolation expectations
- required use of Schneider M580 PLCs

### 5.2 Output model

`ground` outputs:

- `node_patterns`
- `logical_constraints`
- `physical_constraints`

runtime derives:

- `expanded_node_ids`

`ground` does not need to output per-node cards or explicit structured bindings.

### 5.3 Node ID policy

All usable node IDs are produced and frozen in `ground`.

Later stages:

- may not introduce new node IDs
- may not remove node IDs from the available pool
- must design only within the frozen node set

### 5.4 Compact node declarations

`ground` may use compact forms such as:

- `PLC[1..6]`
- `HMI[01..20]`

runtime expands them into canonical node IDs for downstream stages.

### 5.5 Constraint style

Constraints remain expert-readable natural language.

A heavy structured DSL is intentionally avoided.

Constraints may include compact node references inside the text, for example:

- `PLC[1..6] 必须分布在 3 个控制子网中`
- `HMI[1..2] 必须能够访问 PLC[1..6]`

The design goal is natural-language readability with light template discipline rather than full free-form chaos or a heavy formal language.

### 5.6 Ground self-check

Before `ground` is accepted, runtime should verify:

- user intent has been covered
- compact node declarations are valid
- node references inside constraints can be resolved against the frozen node set
- constraints do not reference nonexistent nodes

`ground` does not need a separate self-check for "overstepping logical design." High-level topology scheme articulation is allowed if it is needed to make the user intent executable.

## 6. Constraint Handling

### 6.1 Natural-language-first policy

Constraints should stay as one-by-one natural-language statements because:

- domain experts can read them directly
- they are cheaper than heavyweight structured constraints
- they preserve model flexibility in domain reasoning

### 6.2 Runtime parsing support

runtime should provide a reusable parser for compact node references embedded in natural-language constraints.

This parser is a runtime capability, not a new persisted artifact family.

In particular, runtime should not persist extra artifacts such as:

- `logical_constraint_bindings`
- `physical_constraint_bindings`

The authoritative expression of intent remains the original constraint text.

### 6.3 Template discipline

Although constraints remain natural language, prompts should encourage a small set of stable sentence patterns, for example:

- whole-topology requirements
- node-set requirements
- prohibition requirements
- connectivity requirements
- count requirements

This should improve consistency without introducing a hard DSL.

## 7. Logical Stage

### 7.1 Responsibility

`logical` is the topology design stage.

It should:

- author logical checkpoints
- author or update a logical validator script
- assign logical node roles and types
- build logical ports and links
- realize the high-level scheme implied by `ground`

It must not:

- invent new node IDs
- depend on hidden long-term graph memory

### 7.2 Internal sub-rounds

The initial logical stage is split into two sub-rounds.

#### `logical.check_author`

Inputs:

- user intent
- `ground.expanded_node_ids`
- `ground.logical_constraints`

Outputs:

- `logical_checkpoints`
- `logical_validator_script`

runtime should lightly validate these outputs before graph construction.

#### `logical.graph_builder`

Inputs:

- user intent
- `ground.expanded_node_ids`
- `ground.logical_constraints`
- runtime-generated logical skeleton graph
- current `logical_checkpoints`
- current `logical_validator_script`

Outputs:

- `logical_patch_ops`

runtime applies the patch ops to the working graph and validates the result.

### 7.3 Logical skeleton graph

runtime should create a logical working skeleton before graph construction.

This skeleton:

- includes every frozen node ID
- contains no final links yet
- may leave node `type` unset or `unknown` until logical patches fill it in

This reduces redundant agent output and makes frozen-node semantics runtime-owned rather than prompt-owned.

### 7.4 Logical repair

If validation fails, `logical.repair` receives:

- current authoritative `tgraph_logical`
- current checkpoints
- current validator script
- latest validation report
- repair context

Outputs may include:

- patch ops
- updated checkpoints
- updated validator script

`logical` is allowed to fix its own faulty checkpoints and scripts during repair.

## 8. Physical Stage

### 8.1 Responsibility

`physical` is the deployment-realization stage.

It should:

- author physical checkpoints
- author or update a physical validator script
- map the logical graph into a deployable physical graph
- add physical attributes such as images, flavors, addressing, and deployment details

It must not:

- silently redesign the logical connectivity
- invent new node IDs outside the frozen set

### 8.2 Internal sub-rounds

The initial physical stage is also split into two sub-rounds.

#### `physical.check_author`

Inputs:

- user intent
- `ground.expanded_node_ids`
- `ground.physical_constraints`
- passed `logical.tgraph_logical`
- `logical.logical_checkpoints`

Outputs:

- `physical_checkpoints`
- `physical_validator_script`

#### `physical.graph_builder`

Inputs:

- user intent
- `ground.expanded_node_ids`
- `ground.physical_constraints`
- passed `logical.tgraph_logical`
- runtime-generated physical skeleton graph
- `logical.logical_checkpoints`
- current `physical_checkpoints`
- current `physical_validator_script`

Outputs:

- `physical_patch_ops`

runtime applies patch ops and validates the resulting physical graph.

### 8.3 Physical skeleton graph

runtime should create a physical working skeleton from the passed logical graph.

This skeleton should preserve:

- logical nodes
- logical connectivity

Then `physical` fills in the physical layer details.

### 8.4 Physical boundary rule

`physical` may not change already-approved logical connectivity.

If physical constraints cannot be satisfied without redesigning the logical topology, runtime should surface a stage-boundary failure instead of letting `physical` silently rewrite the graph.

### 8.5 Physical repair

If validation fails, `physical.repair` receives:

- current authoritative `tgraph_physical`
- current checkpoints
- current validator script
- latest validation report
- repair context

Outputs may include:

- patch ops
- updated checkpoints
- updated validator script

As in `logical`, checkpoint and script fixes are allowed.

## 9. Patch Model

### 9.1 Why patch-first

Patch-first design is preferred because full-graph regeneration is too expensive and unstable for large topologies.

### 9.2 Patch layers

The patch system should support two layers.

#### Basic patch ops

- `add_node`
- `update_node`
- `remove_node`
- `add_port`
- `update_port`
- `remove_port`
- `add_link`
- `update_link`
- `remove_link`

#### Higher-level patch ops

These are needed for scale and should be added if the lower-level model becomes too verbose.

Candidate examples:

- pattern-based node expansion helpers
- batch node updates
- set-to-set connectivity helpers
- star-connect helpers
- rule-based port assignment
- segment partition helpers
- batch physical materialization helpers

The design does not require every high-level op on day one, but it explicitly allows and recommends them where scale demands it.

### 9.3 Authority rule

The authoritative graph always lives in runtime storage, not in the model context.

The model proposes changes.
runtime decides what the current graph is.

## 10. Round Outputs vs Final Artifacts

This design distinguishes round outputs from final stage artifacts.

### 10.1 Ground

For `ground`, round output and final artifact are effectively the same.

Persisted artifacts:

- `ground.node_patterns`
- `ground.expanded_node_ids`
- `ground.logical_constraints`
- `ground.physical_constraints`

### 10.2 Logical

Agent round outputs:

- `logical_checkpoints`
- `logical_validator_script`
- `logical_patch_ops`
- optional notes

Final persisted artifacts:

- `logical.logical_checkpoints`
- `logical.logical_validator_script`
- `logical.tgraph_logical`
- optional latest validation report
- optional patch history

### 10.3 Physical

Agent round outputs:

- `physical_checkpoints`
- `physical_validator_script`
- `physical_patch_ops`

Final persisted artifacts:

- `physical.physical_checkpoints`
- `physical.physical_validator_script`
- `physical.tgraph_physical`
- optional latest validation report
- optional patch history

## 11. Repair Loop Design

### 11.1 Outer-loop policy

Repair should be runtime-controlled outer retry, not agent-internal memory looping.

This keeps each round cleaner and prevents old graph versions from contaminating the next attempt.

### 11.2 Minimal repair input set

Repair rounds should receive only what is needed to fix the current state.

For `logical`:

- user intent
- `ground.expanded_node_ids`
- `ground.logical_constraints`
- current `tgraph_logical`
- current checkpoints
- current validator script
- latest validation report
- repair context

For `physical`:

- user intent
- `ground.expanded_node_ids`
- `ground.physical_constraints`
- passed `logical.tgraph_logical`
- current `tgraph_physical`
- current checkpoints
- current validator script
- latest validation report
- repair context

### 11.3 Repair context

Repair context should stay compact and should usually include:

- failed checkpoint IDs
- issue codes
- issue messages
- affected nodes, ports, or links
- affected JSON paths
- graph summary
- most recent patch summary

Full historical validation reports should not be replayed by default.

## 12. Failure Semantics

The runtime should distinguish at least four failure types.

### 12.1 `constraint_parse_error`

The natural-language constraints reference node patterns or node IDs that cannot be resolved against the frozen node set.

This is a `ground`-side failure.

### 12.2 `checkpoint_authoring_error`

The stage-authored checkpoints or validator script are invalid.

Examples:

- unresolved node references
- invalid script structure
- script execution failure caused by authored logic

This is repairable within the current stage.

### 12.3 `graph_repairable_error`

The graph is wrong, incomplete, or inconsistent but can still be repaired by patching.

This is the normal `logical` or `physical` repair path.

### 12.4 `stage_boundary_error`

The current stage discovers a problem whose fix belongs to an earlier stage.

The main example is physical infeasibility that would require redesigning logical connectivity.

In v1, runtime should surface this as an explicit failure rather than automatically rolling back across stages.

## 13. Runtime Changes Required

The current runtime assumes that the agent returns final stage outputs directly.

This design requires runtime to grow the following responsibilities:

- build logical and physical skeleton graphs
- parse compact node references in natural-language constraints
- apply patch operations to working graphs
- validate authored checkpoints and scripts before graph-building when needed
- validate graphs after patch application
- build compact repair contexts
- version checkpoints, scripts, graphs, reports, and patch history
- build round-specific agent requests for initial authoring, graph building, and repair

The key contract change is:

- `ground`: agent output equals final stage output
- `logical` and `physical`: agent output is a round output; runtime assembles the final stage artifacts

## 14. Testing Strategy

### 14.1 Unit tests

- node pattern expansion
- compact reference parsing inside natural-language constraints
- logical skeleton creation
- physical skeleton creation
- basic patch application
- higher-level patch application
- checkpoint and script replacement logic
- repair context summarization
- physical guard against logical-connectivity mutation

### 14.2 Integration tests

- `ground` output plus self-check
- `logical.check_author -> logical.graph_builder -> logical.repair`
- `physical.check_author -> physical.graph_builder -> physical.repair`
- joint use of logical and physical checkpoints during physical validation

### 14.3 Large-topology regression tests

Use workloads such as `PLC[1..100]` to verify:

- patch-first behavior stays viable
- repair rounds stay compact
- runtime does not depend on full-graph re-emission

### 14.4 LLM contract tests

Fake or stub facades should remain in CI, but fixtures should shift from final graph payloads to round-output payloads.

This lets the patch-first runtime mature before depending on real-model tests.

## 15. Rollout Recommendation

Implement this design in the following order:

1. Refactor runtime contracts to support skeleton graphs, round outputs, and patch application
2. Update `ground` to the new node-freezing and natural-language constraint workflow
3. Upgrade prompts and real agent execution paths
4. Add larger-topology tests and repair-loop coverage
5. Leave automatic cross-stage rollback and real translation for later

## 16. Final Recommendation

TRACE should move from fixture-returned final graphs to a real patch-first three-stage runtime.

The recommended principle set is:

- `ground` turns abstract intent into executable constraints
- `logical` decides how the network connects
- `physical` decides how the approved logical network is deployed
- runtime owns graph truth, patch application, and repair control

This gives the project the cleanest path toward real staged execution while staying readable to domain experts and scalable to larger topologies.
