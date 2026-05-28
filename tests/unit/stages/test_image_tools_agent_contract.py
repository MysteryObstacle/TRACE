import pytest
from pydantic import ValidationError

from trace.stages.repair_tools import StageRepairTools
from trace.tools.images.agent_surface import FindImagesInput, coerce_string_list, invoke_find_images


def _seed_physical_artifact():
    return {
        "graph": {
            "stage": "physical",
            "nodes": [
                {"id": "FIREWALL", "type": "computer", "label": "FIREWALL", "ports": [], "image": None, "flavor": None}
            ],
            "links": [],
        },
        "constraint_files": {},
        "checkpoint_files": {},
    }


def test_coerce_string_list_parses_json_array_string():
    assert coerce_string_list('["firewall"]') == ["firewall"]


def test_find_images_input_accepts_roles_json_string():
    parsed = FindImagesInput.model_validate({"roles": '["firewall"]'})
    assert parsed.roles == ["firewall"]


def test_find_images_invoke_accepts_roles_json_string_without_tool_error():
    result = invoke_find_images(roles='["firewall"]', node_type="computer")
    assert result["ok"] is True
    assert any(item["id"] == "pfsense" for item in result["images"])


def test_find_images_tool_invoke_does_not_raise_on_json_string_roles():
    tools = StageRepairTools(_seed_physical_artifact()).as_agent_tools(include_image_tools=True)
    bound = {tool.name: tool for tool in tools}
    result = bound["find_images"].invoke({"roles": '["firewall"]', "node_type": "computer"})
    assert result["ok"] is True
    assert "pfsense" in {item["id"] for item in result["images"]}


def test_list_images_tool_is_exposed_with_image_tools():
    tools = StageRepairTools(_seed_physical_artifact()).as_agent_tools(include_image_tools=True)
    names = {tool.name for tool in tools}
    assert "list_images" in names


def test_find_images_empty_match_returns_suggestions():
    result = invoke_find_images(
        query="xyzzyqwerty_unlikely_token",
        roles=["nonexistent_role_xyz"],
        node_type="computer",
    )
    assert result["ok"] is True
    assert result["images"] == []
    assert result["suggestions"]


def test_find_images_includes_match_reasons():
    result = invoke_find_images(roles=["firewall"], node_type="computer", limit=3)
    match = next(item for item in result["images"] if item["id"] == "pfsense")
    assert match["match_reasons"]
    assert any(reason.startswith("role:") for reason in match["match_reasons"])


def test_get_image_unknown_id_returns_structured_error():
    tools = StageRepairTools(_seed_physical_artifact()).as_agent_tools(include_image_tools=True)
    bound = {tool.name: tool for tool in tools}
    result = bound["get_image"].invoke({"image_id": "not-a-real-image"})
    assert result["ok"] is False
    assert result["error"]["code"] == "unknown_image_id"
    assert result["suggestions"]


def test_find_images_input_rejects_non_coercible_roles():
    with pytest.raises(ValidationError):
        FindImagesInput.model_validate({"roles": {"bad": "shape"}})
