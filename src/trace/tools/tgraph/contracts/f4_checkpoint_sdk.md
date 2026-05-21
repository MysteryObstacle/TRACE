# TGraph F4 Checkpoint SDK

## F4 checkpoint SDK

- The same checkpoint payload shape is used in both logical and physical stages.
- Logical stage uses `logical_checkpoints` and optional `logical_validator_script`.
- Physical stage uses `physical_checkpoints` and optional `physical_validator_script`.

### F4 checkpoint execution model

- F4 executes authored checkpoints, not validator scripts directly.
- Each checkpoint must name exactly one function in `func`.
- The named function is resolved first from the built-in checkpoint SDK, then from public functions defined in the stage validator script.
- A custom validator function runs only when a checkpoint `func` names that function.
- A standalone function such as `logical_validator` or `physical_validator` is not an automatic entry point.
- The validator script is a function library for checkpoints; it is not itself a scheduled check.
- `constraint_ids` are provenance and coverage metadata; they do not change what a checkpoint function checks.
- Attach a constraint id to the checkpoint whose function actually validates that constraint's semantics.
- When `logical_constraints` or `physical_constraints` are supplied, F4 reports authored checkpoints that omit a required constraint id or reference an unknown constraint id.

### Built-in checkpoint functions

1. `connect_nodes(node_a: str, node_b: str)`
   - passes when `node_a` and `node_b` are directly adjacent
2. `switch_has_subnet(switch_id: str, expected_cidr: str)`
   - passes when `switch_id` is a switch and all of its ports carry exactly `expected_cidr` with empty `ip`
   - use this for `Subnet fact: <SWITCH_ID> represents subnet <CIDR>.`
3. `node_interface_on_segment(node_id: str, segment_id: str, expected_ip: str, expected_cidr: str)`
   - passes when `node_id` is directly attached to switch `segment_id` and the node-side port has exactly `expected_ip` and `expected_cidr`
   - use this for `Interface fact: <NODE_ID> uses IP <IP>/<PREFIX> on segment <SWITCH_ID>.`
4. `path_exists(source_id: str, target_id: str)`
   - passes when at least one path exists between source and target
5. `path_must_include(source_id: str, target_id: str, via: str)`
   - passes when at least one source-to-target path includes `via`
