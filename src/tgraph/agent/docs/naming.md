# Naming Rules

Node ids:

- Must match `^[A-Z][A-Z0-9_]*$`.
- Do not use hyphens in node ids.

Link keys:

- Must match `^[A-Za-z0-9_]+$`.
- Must not contain `-`.
- Default key is `1`.
- Use explicit keys when two nodes need multiple links.

Link ids:

- Format: `NODE-NODE-key`.
- The two node ids are sorted by canonical link-id generation.
- Example: `R_CORE-SW_DMZ-1`.

Port ids:

- Node-scoped, not globally meaningful.
- Format: `_PEER-key`.
- Example: on node `R_CORE`, a port toward `SW_DMZ` is `_SW_DMZ-1`.

Interface addressing:

- `ensure_interface(node, segment=SW, cidr=..., ip=...)` sets both endpoint ports to the target CIDR.
- The node-side port may also receive `ip`.
- `ensure_subnet(SW, cidr=...)` sets every existing switch port to that CIDR.
