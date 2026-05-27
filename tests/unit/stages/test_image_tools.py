from trace.stages.repair_tools import StageRepairTools


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


def test_find_images_filters_by_role_when_opt_in():
    tools = StageRepairTools(_seed_physical_artifact()).as_agent_tools(include_image_tools=True)
    bound = {t.name: t for t in tools}
    result = bound["find_images"].invoke({"roles": ["firewall"]})
    ids = [item["image"]["id"] for item in result["images"]]
    assert "img_pfsense" in ids


def test_get_image_returns_image_record_when_opt_in():
    tools = StageRepairTools(_seed_physical_artifact()).as_agent_tools(include_image_tools=True)
    bound = {t.name: t for t in tools}
    result = bound["get_image"].invoke({"image_id": "img_pfsense"})
    assert result["image"]["id"] == "img_pfsense"
    assert result["default_flavor"]["vcpu"] == 2


def test_get_image_unknown_id_returns_error_when_opt_in():
    tools = StageRepairTools(_seed_physical_artifact()).as_agent_tools(include_image_tools=True)
    bound = {t.name: t for t in tools}
    result = bound["get_image"].invoke({"image_id": "img_nonexistent"})
    assert result["ok"] is False
    assert "unknown image" in result["error"]["message"].lower()
