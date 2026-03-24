STAGE_TOOL_MAP = {
    'ground': ['search', 'read_doc', 'list_topics'],
    'logical': ['search', 'read_doc'],
    'physical': ['search', 'read_doc'],
}


def filter_tools_for_stage(stage_id: str, registry: dict[str, object]) -> dict[str, object]:
    allowed = STAGE_TOOL_MAP.get(stage_id, [])
    return {name: registry[name] for name in allowed if name in registry}
