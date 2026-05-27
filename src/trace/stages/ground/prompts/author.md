Your task is to produce a complete `GroundDraftArtifact` that later stages can consume without rereading the original intent.

## Output Contract
- Return only a JSON object with `node_groups`, `logical_constraints`, and `physical_constraints`.
- Each `node_groups` item has only `type` and `members`.
- `type` must be one of `switch`, `router`, or `computer`.
- Each constraint item has `id`, `kind`, and `statement`.
- Do not output `constraint_files`, `graph`, checkpoints, markdown, comments, or explanations.

## Fact Kinds
Use only these logical kinds:
- `logical.addressing.subnet`
- `logical.addressing.interface`
- `logical.topology.direct`
- `logical.topology.chain`
- `logical.topology.ring`
- `logical.topology.star`
- `logical.topology.mesh`
- `logical.custom`

Use only these physical kinds:
- `physical.image.capability`
- `physical.image.exact`
- `physical.flavor.minimum`
- `physical.flavor.exact`
- `physical.custom`

`logical.custom` and `physical.custom` are only for genuinely custom facts that cannot fit the named kinds.

## Statement Rules
- Do not include fact-family prefixes such as `Subnet fact:`, `Interface fact:`, `Graph fact:`, `Image design:`, or `Flavor design:`.
- Keep one executable fact per statement.
- Statements should be concise and concrete.
- Preserve exact user-provided node ids, CIDRs, IPs, chains, and node types.

Examples:
```json
{
  "node_groups": [
    {"type": "switch", "members": ["SW_DMZ"]},
    {"type": "router", "members": ["R_CORE"]},
    {"type": "computer", "members": ["WEB"]}
  ],
  "logical_constraints": [
    {"id": "lc1", "kind": "logical.addressing.subnet", "statement": "SW_DMZ represents subnet 10.10.10.0/24."},
    {"id": "lc2", "kind": "logical.topology.chain", "statement": "explicit chain WEB -> SW_DMZ -> R_CORE."}
  ],
  "physical_constraints": [
    {"id": "pc1", "kind": "physical.image.capability", "statement": "WEB requires web server image capability."}
  ]
}
```

## Grounding Guidance
- Freeze node identity and node type first.
- For explicit direct links, use `logical.topology.direct`.
- For ordered `A -> B -> C` style connectivity, use `logical.topology.chain`.
- For ring, star, and full mesh topology, use the matching topology kind.
- For concrete switch-carried subnet CIDRs, use `logical.addressing.subnet`.
- For concrete fixed interface IPs, use `logical.addressing.interface`.
- For image/appliance/runtime capability requirements, use `physical.image.capability`.
- For exact image ids, use `physical.image.exact`.
- For minimum resource requirements, use `physical.flavor.minimum`.
- For exact flavor requirements, use `physical.flavor.exact`.
- Do not invent CIDRs, IP addresses, image ids, provider placement, firewall rules, software packages, or unsupported graph fields.
