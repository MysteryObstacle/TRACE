from stages.ground.constraint_refs import (
    classify_constraint_family,
    contains_under_grounded_goal,
    contains_vague_node_group,
    resolve_constraint_refs,
)
from stages.ground.normalize import expand_node_patterns
from stages.ground.output_schema import GroundOutput


def assert_valid(output: GroundOutput) -> None:
    if not output.node_patterns:
        raise ValueError("Ground output must include at least one node pattern.")

    available_ids = expand_node_patterns(output.node_patterns)
    covered_ids: set[str] = set()
    for constraint in output.logical_constraints:
        if contains_vague_node_group(constraint.text):
            raise ValueError(f'Ground output contains vague node groups: {constraint.text}')
        if contains_under_grounded_goal(constraint.text):
            raise ValueError(f'Ground output contains under-grounded goal: {constraint.text}')
        covered_ids.update(resolve_constraint_refs(constraint.text, available_ids))
        family = classify_constraint_family(constraint.text, available_ids, is_physical=False)
        if family is None:
            raise ValueError(f'Ground output contains unsupported constraint family: {constraint.text}')

    for constraint in output.physical_constraints:
        if contains_vague_node_group(constraint.text):
            raise ValueError(f'Ground output contains vague node groups: {constraint.text}')
        if contains_under_grounded_goal(constraint.text):
            raise ValueError(f'Ground output contains under-grounded goal: {constraint.text}')
        covered_ids.update(resolve_constraint_refs(constraint.text, available_ids))
        family = classify_constraint_family(constraint.text, available_ids, is_physical=True)
        if family is None:
            raise ValueError(f'Ground output contains unsupported constraint family: {constraint.text}')

    uncovered_ids = [node_id for node_id in available_ids if node_id not in covered_ids]
    if uncovered_ids:
        raise ValueError(f'Ground output contains uncovered frozen nodes: {", ".join(uncovered_ids)}')
