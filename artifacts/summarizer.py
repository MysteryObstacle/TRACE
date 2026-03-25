from __future__ import annotations

from typing import Any

from app.stage_graphs import summarize_patch_ops


def build_repair_context(
    graph: dict[str, Any],
    report: dict[str, Any],
    latest_patch_ops: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    issues = report.get('issues', [])
    related_nodes = sorted({target for issue in issues for target in issue.get('targets', [])})
    open_issues = [f"{issue['code']}: {issue['message']}" for issue in issues]
    link_count = len(graph.get('links', graph.get('edges', [])))
    port_count = sum(len(node.get('ports', [])) for node in graph.get('nodes', []))
    return {
        'graph_summary': {
            'node_count': len(graph.get('nodes', [])),
            'link_count': link_count,
            'port_count': port_count,
        },
        'open_issues': open_issues,
        'related_nodes': related_nodes,
        'json_paths': [path for issue in issues for path in issue.get('json_paths', [])],
        'affected_scopes': sorted({issue.get('scope', 'topology') for issue in issues}),
        'latest_patch_summary': summarize_patch_ops(latest_patch_ops),
    }
