# TGraph Graph Validity

## Validator layers

- F1: top-level format checks
- F2: schema/profile checks
- F3: structural and addressing consistency checks
- F4: authored stage-specific intent checks against the current graph

## Key logical-stage validator expectations

- Each port can participate in at most one link.
- Switch ports:
  - `ip` should be empty
  - `cidr` must be non-empty
  - all switch ports on the same switch should share the same CIDR
- Router ports:
  - `ip` must be non-empty
- If a port has both `ip` and `cidr`, the IP must belong to the CIDR.
- Builder and repair should preserve a graph that remains compatible with F1-F4 for the active stage.

## Implementation default boundary

- F3 checks implementation-complete graph validity, not whether an address was explicitly requested by intent.
- Implementation defaults are graph-validity choices, not intent facts.
- Ground explicit Interface/Subnet facts must be validated by F4 exact checks.
- Builder-created default IP/CIDR values may satisfy F3 without becoming new GroundArtifact constraints.
