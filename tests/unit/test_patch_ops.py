from artifacts.summarizer import build_repair_context
from validators.patching import apply_patch_ops


def test_add_node_patch_updates_tgraph() -> None:
    graph = {'nodes': [], 'edges': []}

    updated = apply_patch_ops(
        graph,
        [{'op': 'add_node', 'value': {'id': 'PLC1'}, 'reason': 'add missing node'}],
    )

    assert updated['nodes'] == [{'id': 'PLC1'}]


def test_build_repair_context_extracts_open_issues() -> None:
    graph = {'nodes': [{'id': 'PLC1'}], 'edges': []}
    report = {
        'ok': False,
        'issues': [
            {
                'code': 'missing_edge',
                'message': 'Edge missing',
                'severity': 'error',
                'scope': 'topology',
                'targets': ['PLC1'],
                'json_paths': ['$.edges'],
            }
        ],
    }

    context = build_repair_context(graph, report)

    assert context['open_issues'] == ['missing_edge: Edge missing']
    assert context['related_nodes'] == ['PLC1']
