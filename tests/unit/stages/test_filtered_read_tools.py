import json

from trace.stages.repair_tools import StageRepairTools


def _seed_artifact():
    return {
        "graph": {"stage": "logical", "nodes": [{"id": "A", "type": "computer", "label": "A", "ports": []}], "links": []},
        "constraint_files": {"logical": "ground/logical_constraints.json"},
        "checkpoint_files": {},
    }


def test_read_support_file_match():
    payload = {f"lc{i}": {"statement": f"lc{i}-stmt", "kind": "logical.custom"} for i in range(1, 18)}
    tools = StageRepairTools(_seed_artifact(), support_files={"ground/logical_constraints.json": json.dumps(payload, indent=2)})
    result = tools.read_support_file(path="ground/logical_constraints.json", match="lc17")
    assert result["ok"] is True
    assert "lc17" in result["content"]
    assert "lc16-stmt" not in result["content"]


def test_read_support_file_keys():
    payload = {"lc1": {"statement": "a"}, "lc17": {"statement": "z"}}
    tools = StageRepairTools(_seed_artifact(), support_files={"ground/logical_constraints.json": json.dumps(payload, indent=2)})
    result = tools.read_support_file(path="ground/logical_constraints.json", keys=["lc17"])
    parsed = json.loads(result["content"])
    assert parsed == {"lc17": {"statement": "z"}}


def test_read_support_file_tool_surface_accepts_filter_params():
    payload = {"lc1": {"statement": "a"}, "lc17": {"statement": "z"}}
    tools = StageRepairTools(_seed_artifact(), support_files={"ground/logical_constraints.json": json.dumps(payload, indent=2)})
    bound = {tool.name: tool for tool in tools.as_agent_tools()}
    result = bound["read_support_file"].invoke({"path": "ground/logical_constraints.json", "match": "lc17"})
    assert "lc17" in result["content"]


def test_logical_author_read_constraint_file_supports_filter():
    from trace.stages.logical.nodes.author import LogicalAuthorTools

    state = {
        "support_files": {
            "ground/logical_constraints.json": json.dumps(
                {"lc1": {"statement": "a"}, "lc17": {"statement": "z"}}, indent=2
            )
        }
    }
    tools = LogicalAuthorTools(state=state, logical_constraints=[{"id": "lc1"}, {"id": "lc17"}]).as_agent_tools()
    bound = {tool.name: tool for tool in tools}
    out = bound["read_constraint_file"].invoke({"path": "ground/logical_constraints.json", "keys": ["lc17"]})
    parsed = json.loads(out["content"])
    assert parsed == {"lc17": {"statement": "z"}}


def test_physical_author_read_constraint_file_supports_filter():
    from trace.stages.physical.nodes.author import PhysicalAuthorTools

    state = {
        "support_files": {
            "ground/physical_constraints.json": json.dumps(
                {"pc1": {"statement": "a"}, "pc2": {"statement": "z"}}, indent=2
            )
        }
    }
    tools = PhysicalAuthorTools(state=state, physical_constraints=[{"id": "pc1"}, {"id": "pc2"}]).as_agent_tools()
    bound = {tool.name: tool for tool in tools}
    out = bound["read_constraint_file"].invoke({"path": "ground/physical_constraints.json", "match": "pc2"})
    assert "pc2" in out["content"]
    assert 'pc1"' not in out["content"]
