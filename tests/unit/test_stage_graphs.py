from app.stage_graphs import build_logical_skeleton, build_physical_skeleton


def test_build_logical_skeleton_includes_all_frozen_nodes() -> None:
    graph = build_logical_skeleton(['PLC1', 'PLC2'])

    assert [node['id'] for node in graph['nodes']] == ['PLC1', 'PLC2']
    assert graph['profile'] == 'logical.v1'
    assert graph['links'] == []


def test_build_physical_skeleton_preserves_logical_connectivity() -> None:
    logical = {
        'profile': 'logical.v1',
        'nodes': [
            {'id': 'PLC1', 'type': 'computer', 'label': 'PLC1', 'ports': [{'id': 'PLC1:p1', 'ip': '', 'cidr': ''}], 'image': None, 'flavor': None},
            {'id': 'SW1', 'type': 'switch', 'label': 'SW1', 'ports': [{'id': 'SW1:p1', 'ip': '', 'cidr': '10.0.0.0/24'}], 'image': None, 'flavor': None},
        ],
        'links': [
            {
                'id': 'PLC1:p1--SW1:p1',
                'from_port': 'PLC1:p1',
                'to_port': 'SW1:p1',
                'from_node': 'PLC1',
                'to_node': 'SW1',
            }
        ],
    }

    graph = build_physical_skeleton(logical)

    assert graph['profile'] == 'taal.default.v1'
    assert [node['id'] for node in graph['nodes']] == ['PLC1', 'SW1']
    assert graph['links'] == logical['links']
