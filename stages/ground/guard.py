from stages.ground.constraint_refs import resolve_constraint_refs
from stages.ground.normalize import expand_node_patterns
from stages.ground.output_schema import GroundOutput


def assert_valid(output: GroundOutput) -> None:
    if not output.node_patterns:
        raise ValueError("Ground output must include at least one node pattern.")

    available_ids = expand_node_patterns(output.node_patterns)
    for constraint in [*output.logical_constraints, *output.physical_constraints]:
        resolve_constraint_refs(constraint.text, available_ids)
