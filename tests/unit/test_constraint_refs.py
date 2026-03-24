import pytest

from stages.ground.guard import assert_valid
from stages.ground.output_schema import GroundOutput


def test_resolve_compact_node_refs_from_constraint_text() -> None:
    from stages.ground.constraint_refs import resolve_constraint_refs

    refs = resolve_constraint_refs(
        text='PLC[1..3] must be split across control segments.',
        available_ids=['PLC1', 'PLC2', 'PLC3', 'HMI1'],
    )

    assert refs == ['PLC1', 'PLC2', 'PLC3']


def test_ground_guard_rejects_unknown_compact_refs() -> None:
    output = GroundOutput(
        node_patterns=['PLC[1..2]'],
        logical_constraints=[{'id': 'lc1', 'scope': 'node_ids', 'text': 'PLC[1..3] must stay isolated.'}],
        physical_constraints=[],
    )

    with pytest.raises(ValueError, match='constraint references unknown nodes'):
        assert_valid(output)
