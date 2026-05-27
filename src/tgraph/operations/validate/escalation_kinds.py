from __future__ import annotations

ESCALATION_ISSUE_KINDS: frozenset[str] = frozenset({
    "logical.escalation.constraint_conflict",
    "logical.escalation.no_satisfying_topology",
    "physical.escalation.no_satisfying_image",
    "physical.escalation.no_satisfying_flavor",
})
