from trace.stages.repair_tools import StageRepairTools


def _seed_logical_artifact():
    return {
        "graph": {"stage": "logical", "nodes": [{"id": "A", "type": "computer", "label": "A", "ports": []}], "links": []},
        "constraint_files": {},
        "checkpoint_files": {},
    }


def test_logical_scope_does_not_expose_image_tools_by_default():
    tools = StageRepairTools(_seed_logical_artifact()).as_agent_tools()
    names = {tool.name for tool in tools}
    assert "find_images" not in names
    assert "get_image" not in names
