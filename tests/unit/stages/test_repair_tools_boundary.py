from trace.stages.repair_tools import StageRepairTools


def _seed_logical_graph_dict() -> dict:
    return {
        "stage": "logical",
        "nodes": [{"id": "SW_DMZ", "type": "switch", "label": "SW_DMZ", "ports": []}],
        "links": [],
    }


def test_builder_repair_tool_surface_excludes_validate_graph():
    tools = StageRepairTools({"graph": _seed_logical_graph_dict(), "constraint_files": {}, "checkpoint_files": {}})
    names = {tool.name for tool in tools.as_agent_tools()}
    assert "validate_graph" not in names


def test_image_tool_surface_includes_list_find_get():
    tools = StageRepairTools({"graph": _seed_logical_graph_dict(), "constraint_files": {}, "checkpoint_files": {}})
    names = {tool.name for tool in tools.as_agent_tools(include_image_tools=True)}
    assert {"list_images", "find_images", "get_image"}.issubset(names)


def test_read_support_file_can_read_image_catalog_json():
    tools = StageRepairTools({"graph": _seed_logical_graph_dict(), "constraint_files": {}, "checkpoint_files": {}})
    result = tools.read_support_file("catalog/image_catalog.v1.json", match="schema_version")
    assert result["ok"] is True
    assert result["path"] == "catalog/image_catalog.v1.json"
    assert '"schema_version": 1' in result["content"]
