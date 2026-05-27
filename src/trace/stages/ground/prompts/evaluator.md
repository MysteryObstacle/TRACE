Your task is to evaluate whether a `GroundDraftArtifact` is semantically ready for later stages.

## Output Contract
- Return only a JSON object matching `GroundEvaluationReport`.
- Fields: `passed` (boolean), `issues` (array), `notes` (array of strings).
- Each issue must be an object with `message`, optional `location`, and `details` containing `issue_kind`.
- When `passed=true`, return empty `issues` and empty `notes`.
- Do **not** return `optimizer_brief` or any nested revision object.

## What You Judge (semantic only)
- Node inventory preserves explicit user node ids and node types.
- Explicit connectivity is represented losslessly (chains, order, intermediate nodes).
- Concrete CIDRs and fixed IPs supplied by the user are retained.
- Do not require CIDRs, IPs, images, or flavors the user did not provide unless you introduced them in an open-ended design.
- Do not mark failed only because optional `physical_constraints` are empty.

## What You Do Not Judge (handled elsewhere)
- Missing/unknown/wrong-scope `kind` values.
- JSON shape, duplicate ids, legacy statement prefixes.
- These appear in `structural_issues` in your context; do not duplicate them unless adding semantic context.

## Recommended Semantic issue_kind Values
- `ground.semantic.missing_node`
- `ground.semantic.missing_chain_step`
- `ground.semantic.dropped_user_cidr`
- `ground.semantic.dropped_user_ip`
- `ground.semantic.added_unauthorized_fact`
- `ground.semantic.redundant_logical_constraint`
- `ground.semantic.redundant_physical_constraint`

## Notes
- Use `notes` for short revision guidance to the author (plain strings).
- Keep notes actionable and specific.
