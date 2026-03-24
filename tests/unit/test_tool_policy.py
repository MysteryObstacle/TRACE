from tools.policy import filter_tools_for_stage
from tools.registry import build_tool_registry


def test_logical_stage_only_sees_allowed_tools() -> None:
    registry = build_tool_registry()
    tools = filter_tools_for_stage('logical', registry)

    assert 'search' in tools
    assert 'read_doc' in tools
    assert 'list_topics' not in tools
