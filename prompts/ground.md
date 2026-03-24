# Ground Stage Prompt

Turn the user's abstract topology request into executable stage artifacts.

Requirements:

- output `node_patterns`, `logical_constraints`, and `physical_constraints` as JSON
- freeze the full usable node set through compact node patterns such as `PLC[1..20]`
- keep constraints expert-readable natural language
- constraints may include compact node references such as `PLC[1..6]`
- use domain knowledge to make the user's abstract intent executable
- do not return per-node cards or a full graph
- make `logical_constraints` about topology and connectivity only
- make `physical_constraints` about deployment properties such as image, flavor, model, or physical placement
