import pytest

from stages.ground.guard import assert_valid
from stages.ground.output_schema import GroundOutput, sanitize_ground_output


def test_resolve_compact_node_refs_from_constraint_text() -> None:
    from stages.ground.constraint_refs import resolve_constraint_refs

    refs = resolve_constraint_refs(
        text='PLC[1..3] must be split across control segments.',
        available_ids=['PLC1', 'PLC2', 'PLC3', 'HMI1'],
    )

    assert refs == ['PLC1', 'PLC2', 'PLC3']


def test_detects_vague_group_phrase() -> None:
    from stages.ground.constraint_refs import contains_vague_node_group

    assert contains_vague_node_group('All PLC nodes must use image X.') is True
    assert contains_vague_node_group('PLC[1..3] must use image X.') is False


def test_detects_under_grounded_goal_phrase() -> None:
    from stages.ground.constraint_refs import contains_under_grounded_goal

    assert contains_under_grounded_goal('The topology must be divided into four segments.') is True
    assert contains_under_grounded_goal('PLC[1..3] must use cidr 10.10.30.0/24.') is False


def test_classifies_graph_level_constraint_family() -> None:
    from stages.ground.constraint_refs import classify_constraint_family

    family = classify_constraint_family(
        text='The whole logical topology must be connected.',
        available_ids=['PLC1', 'SW1'],
        is_physical=False,
    )

    assert family == 'graph-level'


def test_classifies_set_level_constraint_family() -> None:
    from stages.ground.constraint_refs import classify_constraint_family

    family = classify_constraint_family(
        text='PLC[1..3] must use cidr 10.10.30.0/24.',
        available_ids=['PLC1', 'PLC2', 'PLC3'],
        is_physical=False,
    )

    assert family == 'set-level'


def test_classifies_relationship_level_constraint_family() -> None:
    from stages.ground.constraint_refs import classify_constraint_family

    family = classify_constraint_family(
        text='WEB must connect to R_CORE through SW_DMZ.',
        available_ids=['WEB', 'R_CORE', 'SW_DMZ'],
        is_physical=False,
    )

    assert family == 'relationship-level'


def test_classifies_physical_constraint_family() -> None:
    from stages.ground.constraint_refs import classify_constraint_family

    family = classify_constraint_family(
        text='PLC[1..3] must use image openplc-v3.',
        available_ids=['PLC1', 'PLC2', 'PLC3'],
        is_physical=True,
    )

    assert family == 'physical'


def test_classifies_physical_constraint_family_with_natural_image_phrase() -> None:
    from stages.ground.constraint_refs import classify_constraint_family

    family = classify_constraint_family(
        text='PLC[1..3] and HMI1 must use an OpenPLC-compatible image.',
        available_ids=['PLC1', 'PLC2', 'PLC3', 'HMI1'],
        is_physical=True,
    )

    assert family == 'physical'


def test_ground_guard_rejects_unknown_compact_refs() -> None:
    output = GroundOutput(
        node_patterns=['PLC[1..2]'],
        logical_constraints=[{'id': 'lc1', 'scope': 'node_ids', 'text': 'PLC[1..3] must stay isolated.'}],
        physical_constraints=[],
    )

    with pytest.raises(ValueError, match='constraint references unknown nodes'):
        assert_valid(output)


def test_ground_output_normalizes_string_constraints_to_items() -> None:
    output = GroundOutput.model_validate(
        {
            'node_patterns': ['PLC[1..2]'],
            'logical_constraints': ['PLC[1..2] must remain connected.'],
            'physical_constraints': ['All PLCs must use OpenPLC.'],
        }
    )

    assert output.logical_constraints[0].id == 'lc1'
    assert output.logical_constraints[0].text == 'PLC[1..2] must remain connected.'
    assert output.logical_constraints[0].scope == 'node_ids'
    assert output.physical_constraints[0].id == 'pc1'


def test_ground_guard_rejects_vague_group_phrases() -> None:
    output = GroundOutput(
        node_patterns=['PLC[1..2]'],
        logical_constraints=[],
        physical_constraints=[
            {
                'id': 'pc1',
                'scope': 'topology',
                'text': 'All PLC nodes must use an OpenPLC-compatible image.',
            }
        ],
    )

    with pytest.raises(ValueError, match='vague node groups'):
        assert_valid(output)


def test_ground_guard_rejects_under_grounded_segment_goal() -> None:
    output = GroundOutput(
        node_patterns=['PLC[1..2]', 'SW1'],
        logical_constraints=[
            {
                'id': 'lc1',
                'scope': 'topology',
                'text': 'The topology must be divided into four segments.',
            }
        ],
        physical_constraints=[],
    )

    with pytest.raises(ValueError, match='under-grounded'):
        assert_valid(output)


def test_ground_guard_rejects_unclassified_logical_constraint() -> None:
    output = GroundOutput(
        node_patterns=['PLC1'],
        logical_constraints=[
            {
                'id': 'lc1',
                'scope': 'node_ids',
                'text': 'PLC1 must be properly arranged.',
            }
        ],
        physical_constraints=[],
    )

    with pytest.raises(ValueError, match='unsupported constraint family'):
        assert_valid(output)


def test_sanitize_ground_output_moves_topological_physical_constraints_to_logical() -> None:
    output = GroundOutput.model_validate(
        {
            'node_patterns': ['PLC[1..2]', 'SW1'],
            'logical_constraints': [],
            'physical_constraints': [
                {'id': 'pc1', 'scope': 'topology', 'text': 'SW1 must be used to interconnect PLC[1..2].'},
            ],
        }
    )

    sanitized = sanitize_ground_output(output)

    assert sanitized.physical_constraints == []
    assert sanitized.logical_constraints[0].text == 'SW1 must be used to interconnect PLC[1..2].'


def test_sanitize_ground_output_drops_unsupported_switch_capability_constraints() -> None:
    output = GroundOutput.model_validate(
        {
            'node_patterns': ['PLC[1..2]', 'SW1'],
            'logical_constraints': [],
            'physical_constraints': [
                {'id': 'pc1', 'scope': 'topology', 'text': 'SW1 must be configured as a managed switch supporting VLANs.'},
            ],
        }
    )

    sanitized = sanitize_ground_output(output)

    assert sanitized.physical_constraints == []


def test_sanitize_ground_output_preserves_under_grounded_segment_constraint() -> None:
    output = GroundOutput.model_validate(
        {
            'node_patterns': ['PLC[1..6]', 'SW1'],
            'logical_constraints': [
                {'id': 'lc1', 'scope': 'node_ids', 'text': 'PLC[1..6] must be distributed across at least 2 control segments.'},
            ],
            'physical_constraints': [],
        }
    )

    sanitized = sanitize_ground_output(output)

    assert sanitized.logical_constraints[0].text == 'PLC[1..6] must be distributed across at least 2 control segments.'


def test_sanitize_ground_output_does_not_rescue_under_grounded_segment_goal() -> None:
    output = GroundOutput.model_validate(
        {
            'node_patterns': ['PLC[1..6]', 'SW1'],
            'logical_constraints': [
                {
                    'id': 'lc1',
                    'scope': 'node_ids',
                    'text': 'PLC[1..6] must be distributed across at least 2 control segments.',
                }
            ],
            'physical_constraints': [],
        }
    )

    sanitized = sanitize_ground_output(output)

    assert sanitized.logical_constraints[0].text == 'PLC[1..6] must be distributed across at least 2 control segments.'


def test_ground_guard_requires_key_node_coverage() -> None:
    output = GroundOutput(
        node_patterns=['PLC1', 'SW1'],
        logical_constraints=[
            {
                'id': 'lc1',
                'scope': 'node_ids',
                'text': 'PLC1 must connect to SW1 through SW1.',
            }
        ],
        physical_constraints=[],
    )

    assert_valid(output)


def test_ground_guard_rejects_uncovered_frozen_node() -> None:
    output = GroundOutput(
        node_patterns=['PLC1', 'SW1', 'FW1'],
        logical_constraints=[
            {
                'id': 'lc1',
                'scope': 'node_ids',
                'text': 'PLC1 must connect to SW1 through SW1.',
            }
        ],
        physical_constraints=[],
    )

    with pytest.raises(ValueError, match='uncovered frozen nodes'):
        assert_valid(output)
