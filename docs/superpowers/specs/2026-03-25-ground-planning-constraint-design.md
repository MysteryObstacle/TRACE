# TRACE Ground Planning Constraint Design

Date: 2026-03-25
Status: Draft approved in conversation, written for review
Scope: strengthen the `ground` stage so it completes topology planning before freezing nodes and emitting constraints

## 1. Summary

This document refines the `ground` stage design without changing its persisted output schema.

`ground` should continue to output only:

- `node_patterns`
- `logical_constraints`
- `physical_constraints`

However, these outputs must no longer be treated as lightweight intent restatements.

The revised rule is:

`ground` must first finish enough topology planning to make the request executable, then compress that planning into constrained natural-language artifacts.

This change is needed because downstream stages are already designed around frozen node IDs. If `ground` under-plans the topology and omits needed infrastructure nodes, `logical` cannot recover later without violating the frozen-node rule.

## 2. Problem Statement

The current `ground` behavior is too weak in two ways.

### 2.1 Planning may stop too early

The stage can emit abstract constraints without first resolving the actual topology scheme.

That causes a failure mode where:

1. user intent implies a specific structure
2. `ground` freezes an incomplete node set
3. `logical` discovers that routers, switches, firewalls, management hosts, or transit segments are missing
4. `logical` is not allowed to add nodes
5. the run becomes unrecoverable

### 2.2 Constraint wording is too loose

The stage currently permits overly abstract or ambiguous language such as:

- `All PLC nodes must use an OpenPLC-compatible image.`
- `topology must be divided into four segments`

These are readable, but they are not constrained enough for deterministic validation or reliable downstream graph construction.

## 3. Goals

### 3.1 In scope

- Keep the persisted `ground` schema unchanged
- Require `ground` to complete executable topology planning before freezing nodes
- Tighten constraint language into a constrained natural-language style
- Make node-targeting constraints reference explicit node IDs, explicit node lists, or range expressions
- Let address planning be represented inside `logical_constraints`
- Strengthen `ground` guard checks to reject obviously under-grounded outputs
- Update prompt examples so they match the new contract

### 3.2 Out of scope

- Adding a new persisted `topology_plan` artifact
- Replacing natural-language constraints with a formal DSL
- Letting `logical` add missing nodes later
- Performing full semantic parsing or advanced NLP inside `ground` guard

## 4. Chosen Design

Three design directions were considered:

1. prompt-only tightening
2. keep the schema, but harden the semantics of the current three fields
3. add a separate planning artifact

The selected design is option 2.

`ground` keeps the same external schema, but its outputs now mean:

- `node_patterns`: the full frozen node inventory needed to realize the planned topology
- `logical_constraints`: topology, addressing, and segmentation constraints that already reflect a planned design
- `physical_constraints`: deployment constraints that already reflect a planned design

## 5. Ground Responsibility

`ground` is not a simple intent-to-constraint rewrite stage.

It must:

- interpret abstract user goals
- use domain knowledge to derive missing but necessary topology structure
- decide the infrastructure nodes required to realize that structure
- freeze all usable node IDs
- emit constraints that represent the planned result rather than the original abstract wording

Examples of planning that `ground` is expected to complete:

- deciding whether routers, switches, firewalls, HMIs, PLCs, engineering workstations, or management hosts are needed
- deciding whether explicit transit segments are needed
- deciding whether multiple subnets are required
- deciding where isolation or trunk connectivity must exist

If the user asks for a topology that implicitly requires backbone nodes or intermediary infrastructure, those nodes must already appear in `node_patterns`.

## 6. Constraint Language

Constraints remain expert-readable natural language, but they are no longer fully free-form.

The design uses constrained natural language with four allowed semantic families:

- graph-level constraints
- set-level constraints
- relationship-level constraints
- physical constraints

These are not separate persisted lists. They remain mixed inside `logical_constraints` or `physical_constraints` as appropriate.

Every emitted constraint must clearly belong to exactly one family.

Within the current schema, the intended mapping is:

- `logical_constraints` may contain only:
  - graph-level constraints
  - set-level constraints
  - relationship-level constraints
- `physical_constraints` may contain only:
  - physical constraints

### 6.1 Graph-level rule

Graph-level constraints describe properties of the topology as a whole rather than a particular node set.

Typical examples:

- `The whole logical topology must be connected.`
- `The whole topology must contain 50 nodes.`

Graph-level constraints are allowed to omit explicit node IDs only when the property is genuinely about the whole graph and can be checked directly at graph scope.

They must not be used as a hiding place for under-planned structure. For example:

- `The topology must be divided into four segments.`

is not acceptable as a final graph-level constraint unless the segmentation intent is already reduced to executable node-set, routing, CIDR, or isolation rules elsewhere.

### 6.2 Set-level rule

Set-level constraints target one node, an explicit node list, or a compact node range and impose non-path properties on that set.

Typical examples:

- `PLC[1..3]/DCS1 must use cidr 10.10.30.0/24.`
- `R_CORE and FIREWALL must use transit cidr 10.0.0.0/30 between them.`
- `WEB/PC1/PC2 must not be in the same subnet as PLC1.`

Set-level constraints are the main landing place for grounded addressing and segmentation rules after abstract goals have been refined.

### 6.3 Node-targeting rule

Any node-targeting constraint must reference one of the following:

- a single node ID
- an explicit node list
- a compact range expression such as `PLC[1..6]`

The following style is forbidden:

- `All PLC nodes ...`
- `all office hosts ...`
- `the firewall devices ...`

Those phrases are too ambiguous for deterministic downstream processing.

### 6.4 Relationship wording rule

Topology backbones and path requirements should use stable sentence forms such as:

- `WEB must connect to R_CORE through SW_DMZ.`
- `R_CORE must connect to FIREWALL through SW_CORE_FW.`
- `BPC1 must connect to R_CORE through SW_BRANCH and R_BRANCH.`

The exact wording can vary slightly, but the sentence must clearly name:

- the endpoint node or node set
- the intermediary node or node set
- the destination node or node set

Relationship-level constraints should be used when the important requirement is a path, adjacency prohibition, or explicit structural role in the backbone.

### 6.5 Addressing rule

Address planning belongs in `logical_constraints`, not in a separate artifact.

However, addressing must still be grounded through explicit node or node-set references, for example:

- `PLC[1..3]/DCS1 must use cidr 10.10.30.0/24.`
- `R_CORE and FIREWALL must use transit cidr 10.0.0.0/30 between them.`

High-level addressing goals such as `the topology must have four logical subnets` are not enough by themselves unless they are already reducible to graph-checkable rules.

In practice, most grounded addressing statements become set-level constraints.

### 6.6 Physical wording rule

Physical constraints should reference explicit node IDs or node sets, for example:

- `PLC[1..6] must use an OpenPLC-compatible image.`
- `FIREWALL must use a firewall-capable image.`

Prompt examples and docs should stop using vague forms like `All PLC nodes`.

## 7. Grounding Depth Rule

The stage should keep refining high-level requirements until each one becomes executable.

The governing rule is:

Each emitted constraint must satisfy at least one of the following:

- it can be directly checked by a future checkpoint
- it can clearly be realized by `logical` or `physical` and then checked

If neither condition holds, the requirement is still under-grounded and should be refined further before `ground` returns.

Examples:

- `The whole logical topology must be connected.` can stay as a graph-level constraint because it is directly checkable.
- `The topology must be divided into four segments.` is usually too abstract and should be refined into node-set, CIDR, routing, and isolation constraints.

## 8. Coverage Rule

Because `ground` freezes all usable nodes, the stage must avoid introducing nodes with no clear purpose.

The design therefore requires:

- every key frozen node must be covered by at least one constraint
- coverage may be direct or via a relationship constraint that clearly assigns the node a structural role

This rule is meant to catch situations where `ground` invents extra infrastructure but never actually uses it in the planned design.

## 9. Prompt Requirements

`prompts/ground.md` should be updated to reflect the stronger contract.

The prompt should explicitly say:

- complete the topology plan before returning output
- include all infrastructure nodes needed to realize the planned design
- never target vague groups like `All PLC nodes`
- prefer explicit node IDs, explicit node lists, or compact range expressions
- use stable sentence forms for relationship constraints
- continue refining any high-level requirement until it becomes executable

The prompt should also include representative recommended sentence forms such as:

- `The whole logical topology must be connected.`
- `X must use cidr Y.`
- `X must connect to Z through Y.`
- `X must not directly connect to Y.`
- `X must use image Y.`

The prompt examples should be corrected so that vague phrases like:

- `All PLC nodes must use an OpenPLC-compatible image.`

become:

- `PLC[1..6] must use an OpenPLC-compatible image.`

## 10. Guard Requirements

`stages/ground/guard.py` should be upgraded from simple reference resolution to light structural validation.

The new guard should remain deterministic and should avoid heavy NLP.

Recommended checks:

- `node_patterns` must be non-empty
- `node_patterns` must expand successfully
- every explicit node or range reference in constraint text must resolve against the frozen node set
- clearly vague group phrases should be rejected
- key frozen nodes should be covered by at least one constraint
- clearly under-grounded high-level phrases should be rejected when they are not accompanied by executable detail

The guard should focus on obvious bad outputs, not on full semantic understanding.

## 11. Runtime Compatibility

This design intentionally avoids adding new persisted artifacts.

No changes are required to the current persisted `ground` artifact contract:

- `ground.node_patterns`
- `ground.expanded_node_ids`
- `ground.logical_constraints`
- `ground.physical_constraints`

The main changes are semantic and validation-oriented:

- stronger prompt contract
- stronger guard contract
- stronger examples
- stronger tests

## 12. Testing Strategy

Tests should be added or updated for the following:

- legal explicit range references such as `PLC[1..6]`
- rejection of vague group phrases such as `All PLC nodes`
- rejection of unresolved compact references
- rejection of obviously under-grounded high-level goals
- coverage checks for frozen key nodes
- prompt/example alignment for explicit node-set wording

## 13. Final Recommendation

Keep the `ground` schema unchanged, but redefine the stage as a topology-planning stage that must finish enough design work before freezing nodes.

In short:

- `ground` must plan first
- `ground` must freeze all required nodes
- `ground` must emit executable constrained natural-language constraints
- `ground` must reject vague or under-grounded outputs

This is the smallest design change that closes the current missing-node failure mode without adding a new artifact layer.
