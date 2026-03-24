from __future__ import annotations

from typing import Any


def build_repair_context(graph: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    issues = report.get('issues', [])
    related_nodes = sorted(
        {target for issue in issues for target in issue.get('targets', [])}
    )
    open_issues = [f"{issue['code']}: {issue['message']}" for issue in issues]
    return {
        'graph_summary': {
            'node_count': len(graph.get('nodes', [])),
            'edge_count': len(graph.get('edges', [])),
        },
        'open_issues': open_issues,
        'related_nodes': related_nodes,
        'json_paths': [path for issue in issues for path in issue.get('json_paths', [])],
    }
