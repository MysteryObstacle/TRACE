# Ground Stage Prompt

Turn the user's abstract topology request into executable stage artifacts.

Return exactly one JSON object. Do not add Markdown fences. Do not add explanations before or after the JSON.

The real user request is provided in `runtime.intent`.
Treat every JSON snippet in this prompt as an illustrative schema example only. Do not copy example values unless they are truly required by `runtime.intent`.

You must finish enough topology planning before returning output. Do not merely restate the user's abstract intent.

The output schema is unchanged. The values below are placeholders, not a few-shot target to copy:

```json
{
  "node_patterns": ["NODE_A", "NODE_B", "INFRA_1"],
  "logical_constraints": [
    {
      "id": "lc1",
      "scope": "topology",
      "text": "The whole logical topology must be connected."
    },
    {
      "id": "lc2",
      "scope": "node_ids",
      "text": "NODE_A must connect to NODE_B through INFRA_1."
    },
    {
      "id": "lc3",
      "scope": "node_ids",
      "text": "NODE_A must use cidr 10.10.30.0/24."
    }
  ],
  "physical_constraints": [
    {
      "id": "pc1",
      "scope": "node_ids",
      "text": "NODE_A must use image openplc-v3."
    }
  ]
}
```

Requirements:

- `node_patterns` must freeze the full usable node set through compact node patterns such as `PLC[1..20]`
- `node_patterns` must include all infrastructure nodes needed to realize the planned design, such as switches, routers, firewalls, engineering workstations, or servers
- do not write constraints that require nodes or devices that are not present in `node_patterns`
- each constraint item must be an object with `id`, `scope`, and `text`
- `scope` must be either `node_ids` or `topology`
- keep `text` expert-readable natural language
- constraints may include compact node references such as `PLC[1..6]`
- do not return per-node cards or a full graph

Planning rules:

- finish topology planning before freezing nodes
- refine high-level goals until they become executable
- if the user intent implies routers, switches, firewalls, transit segments, or management hosts, include them in `node_patterns`
- if a high-level goal cannot be directly checked later, keep refining it until it becomes a graph-realizable constraint
- examples of acceptable high-level constraints:
  - `The whole logical topology must be connected.`
  - `The whole topology must contain 50 nodes.`
- examples of unacceptable under-grounded goals:
  - `The topology must be divided into four segments.` unless you also ground that into concrete node-set, cidr, routing, or isolation constraints

Constraint language rules:

- every emitted constraint must clearly belong to exactly one of these semantic families:
  - `graph-level constraints`
  - `set-level constraints`
  - `relationship-level constraints`
  - `physical constraints`
- any node-targeting constraint must reference explicit node IDs, explicit node lists, or compact ranges such as `PLC[1..6]`
- do not use vague node-group phrases such as:
  - `All PLC nodes`
  - `all office hosts`
  - `the firewall devices`
- use stable sentence forms whenever possible

Recommended sentence families:

- graph-level constraints:
  - `The whole logical topology must be connected.`
  - `The whole topology must contain 50 nodes.`
- set-level constraints:
  - `X must use cidr Y.`
  - `X and Y must use transit cidr Z between them.`
- relationship-level constraints:
  - `X must connect to Z through Y.`
  - `X must not directly connect to Y.`
- physical constraints:
  - `X must use image Y.`
  - `X must use model Y.`
  - `X must use flavor Y.`

Logical constraint rules:

- make `logical_constraints` about topology, connectivity, addressing, routing intent, isolation, segmentation, or topology-wide graph properties
- each logical constraint must fall into one of these families:
  - `graph-level constraints`
  - `set-level constraints`
  - `relationship-level constraints`
- address planning belongs in `logical_constraints`
- express addressing through nodes or node sets, for example:
  - `PLC[1..3]/DCS1 must use cidr 10.10.30.0/24.`
  - `R_CORE and FW1 must use transit cidr 10.0.0.0/30 between them.`

Physical constraint rules:

- make `physical_constraints` about deployment properties such as image, flavor, model, or physical placement
- every physical constraint must belong to the `physical constraints` family and must reference explicit nodes or explicit node sets
- only write physical constraints that can be expressed by the current physical graph schema
- current physical schema can reliably represent:
  - `image` and `flavor` for nodes modeled as `computer`
  - existing node identity and logical links inherited from the logical stage
- do not emit physical constraints about unsupported fields such as switch feature flags, VLAN capability metadata, arbitrary appliance capabilities, or custom properties that are not part of the node schema
- do not emit physical constraints that target switch-specific capabilities
- if a switch is needed, capture its role through logical connectivity constraints instead of unsupported physical capability claims

Final grounding rule:

- every key node you freeze should be clearly covered by at least one constraint
- every emitted constraint must either be directly checkable later or clearly realizable by later graph construction and then checkable
