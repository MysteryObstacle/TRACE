# Ground Grounding Redesign Design

## Goal

Redesign the ground-stage artifact and prompts so ground focuses on turning high-level intent into an executable topology/deployment plan, while logical and physical stages keep ownership of compiling that plan into checkpoints, validator scripts, and graph changes.

## Approved Decisions

- Replace `node_blueprints` with `node_groups`.
- Replace `pattern` with `members`.
- Keep `logical_constraints` and `physical_constraints` minimal:
  - `id`
  - `statement`
- Do not keep backward compatibility for the old ground artifact fields.
- Put the main intelligence in the ground-stage prompts and evaluator, not in a large constraint taxonomy.

## Why This Change

The current ground artifact is structurally valid but not prompt-friendly:

- `pattern` is easy for the model to misread as a matching rule or regex instead of a canonical node identity declaration.
- `pattern + type` repeated per row is noisier than grouping canonical members under a shared node type.
- `scope` inside constraints adds schema weight without adding meaningful grounding guidance.
- Free-text constraints are currently too weakly guided, so ground may restate intent instead of producing an executable plan.

This redesign keeps the schema simple and stable while making the prompts much stricter about what a valid grounded plan looks like.

## Target Ground Artifact

```json
{
  "node_groups": [
    {
      "type": "switch",
      "members": ["Switch1"]
    },
    {
      "type": "router",
      "members": ["Gateway1"]
    },
    {
      "type": "computer",
      "members": ["OpenPLC1", "PLC[1..3]", "HMI1"]
    }
  ],
  "logical_constraints": [
    {
      "id": "lc1",
      "statement": "OpenPLC1 and PLC1..3 must directly connect to Switch1."
    }
  ],
  "physical_constraints": [
    {
      "id": "pc1",
      "statement": "OpenPLC1 must use an OpenPLC image."
    }
  ]
}
```

## Stage Boundary

Ground owns:

- inferring the concrete plan implied by intent
- freezing canonical node identities and necessary infrastructure
- writing explicit, executable logical and physical constraints

Ground does not own:

- authoring checkpoints
- authoring validator scripts
- editing TGraph topology
- binding constraints to specific F4 helper functions

Logical and physical authors continue to infer how best to compile grounded constraints into checkpoints and validator scripts.

## Prompt Direction

The ground author prompt should force this sequence:

1. infer the design plan first
2. freeze canonical node groups
3. express the plan as executable constraints

The prompt must emphasize that a good constraint is not a slogan or a restatement of intent. It must be specific enough that downstream author/builder nodes can act on it directly without returning to the original user intent for missing semantics.

The evaluator prompt should judge readiness using this question:

> Is the artifact sufficient for downstream logical and physical stages to execute against it with minimal ambiguity?

## Constraint Quality Rules

Logical or physical statements should:

- use explicit canonical node ids or compact canonical ranges
- describe one executable fact per statement
- avoid vague groups unless expanded in the same statement
- stay in their stage lane
- be specific enough to drive checkpoint authoring or builder reasoning

Bad:

- "The control network should be secure and isolated."
- "PLCs should be deployed correctly."

Good:

- "PLC1..3 and HMI1 must share subnet 192.168.10.0/24 via Switch1."
- "OfficePC1 may reach Historian1 only through Firewall1."
- "OpenPLC1 must use an OpenPLC image."

## Implementation Scope

- update ground schemas and normalizers
- update derive helpers to consume `node_groups`
- update logical stage preparation and prompts to consume the new ground artifact
- update physical stage prompts/examples that mention ground fields
- update tests and architecture docs that reference the old fields

## Non-Goals

- adding a rich ground constraint taxonomy
- emitting checkpoint-ready structures from ground
- preserving old field compatibility
