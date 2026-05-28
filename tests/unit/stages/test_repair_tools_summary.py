from trace.stages.repair_tools import MutationSummary, StageRepairTools, _derive_op_counts


def test_derive_op_counts_aggregates_by_op_name():
    operations = [
        {"op": "ensure_direct_link", "link": "A-B-1", "nodes": ["A", "B"], "link_key": "1"},
        {"op": "ensure_direct_link", "link": "B-C-1", "nodes": ["B", "C"], "link_key": "1"},
        {"op": "set_image", "node": "A", "image_id": "pfsense"},
    ]
    assert _derive_op_counts(operations) == {"ensure_direct_link": 2, "set_image": 1}


def test_mutation_summary_affected_node_ids_from_scalar_and_list_fields():
    operations = [
        {"op": "ensure_node", "node": "A"},
        {"op": "ensure_direct_link", "link": "A-B-1", "nodes": ["A", "B"]},
        {"op": "set_image", "node": "B", "image_id": "pfsense"},
        {"op": "ensure_interface", "node": "C", "segment": "B", "cidr": "10.0.0.0/24", "ip": None},
        {"op": "remove_links", "links_removed": ["X-Y-1"], "ports_removed": ["X._Y-1", "Y._X-1"]},
    ]
    summary = MutationSummary.from_operations(stage="logical", node_count=10, link_count=8, operations=operations)
    assert summary.affected_node_ids == ["A", "B", "C", "X", "Y"]
    assert summary.affected_link_ids == ["A-B-1", "X-Y-1"]
    assert summary.op_counts == {
        "ensure_node": 1,
        "ensure_direct_link": 1,
        "set_image": 1,
        "ensure_interface": 1,
        "remove_links": 1,
    }


def _seed_logical_graph_dict() -> dict:
    return {
        "stage": "logical",
        "nodes": [
            {"id": "SW_DMZ", "type": "switch", "label": "SW_DMZ", "ports": []},
        ],
        "links": [],
    }


def test_execute_mutation_file_returns_summary_only_by_default(tmp_path):
    artifact = {"graph": _seed_logical_graph_dict(), "constraint_files": {}, "checkpoint_files": {}}
    tools = StageRepairTools(artifact, support_file_root=str(tmp_path))
    write = tools.write_mutation_file(
        content="def mutate(tgraph):\n    tgraph.ensure_subnet('SW_DMZ', cidr='10.10.10.0/24')\n",
        path="logical/mutations/test.py",
    )
    result = tools.execute_mutation_file(path=write["path"], validate=False)
    assert result["ok"] is True
    assert "summary" in result
    assert "graph" not in result
    assert "operations" not in result
    assert result["summary"]["op_counts"] == {"ensure_subnet": 1}


def test_execute_mutation_file_includes_graph_when_requested(tmp_path):
    artifact = {"graph": _seed_logical_graph_dict(), "constraint_files": {}, "checkpoint_files": {}}
    tools = StageRepairTools(artifact, support_file_root=str(tmp_path))
    write = tools.write_mutation_file(
        content="def mutate(tgraph):\n    tgraph.ensure_subnet('SW_DMZ', cidr='10.10.10.0/24')\n",
        path="logical/mutations/test.py",
    )
    result = tools.execute_mutation_file(path=write["path"], validate=False, include_graph=True)
    assert "graph" in result
    assert result["graph"]["stage"] == "logical"


def test_execute_mutation_file_defaults_to_no_validation(tmp_path):
    checkpoint_path = tmp_path / "logical" / "checkpoints.py"
    checkpoint_path.parent.mkdir(parents=True)
    checkpoint_path.write_text(
        "def check_lc1(tgraph):\n    return tgraph.check_direct_link('SW_DMZ', 'MISSING')\n",
        encoding="utf-8",
    )
    artifact = {
        "graph": _seed_logical_graph_dict(),
        "constraint_files": {},
        "checkpoint_files": {"logical": "logical/checkpoints.py"},
    }
    tools = StageRepairTools(
        artifact,
        support_files={"logical/checkpoints.py": checkpoint_path.read_text(encoding="utf-8")},
        support_file_root=str(tmp_path),
    )
    write = tools.write_mutation_file(content="def mutate(tgraph):\n    pass\n")

    result = tools.execute_mutation_file(path=write["path"])

    assert result["ok"] is True
    assert "issues" not in result


def test_execute_mutation_file_agent_tool_exposes_validate_parameter():
    tools = StageRepairTools({"graph": _seed_logical_graph_dict(), "constraint_files": {}, "checkpoint_files": {}})
    bound = {tool.name: tool for tool in tools.as_agent_tools()}

    assert "validate" in bound["execute_mutation_file"].args
    assert "run_validate" not in bound["execute_mutation_file"].args
    assert bound["execute_mutation_file"].args["validate"]["default"] is False


def test_execute_mutation_file_can_still_run_validation_when_requested(tmp_path):
    constraints_path = tmp_path / "ground" / "logical_constraints.json"
    constraints_path.parent.mkdir(parents=True)
    constraints_path.write_text(
        '{"lc1": {"kind": "logical.topology.direct", "statement": "SW_DMZ must connect to MISSING."}}',
        encoding="utf-8",
    )
    checkpoint_path = tmp_path / "logical" / "checkpoints.py"
    checkpoint_path.parent.mkdir(parents=True)
    checkpoint_path.write_text(
        "def check_lc1(tgraph):\n    return tgraph.check_direct_link('SW_DMZ', 'MISSING')\n",
        encoding="utf-8",
    )
    artifact = {
        "graph": _seed_logical_graph_dict(),
        "constraint_files": {"logical": "ground/logical_constraints.json"},
        "checkpoint_files": {"logical": "logical/checkpoints.py"},
    }
    tools = StageRepairTools(
        artifact,
        support_files={
            "ground/logical_constraints.json": constraints_path.read_text(encoding="utf-8"),
            "logical/checkpoints.py": checkpoint_path.read_text(encoding="utf-8"),
        },
        support_file_root=str(tmp_path),
    )
    write = tools.write_mutation_file(content="def mutate(tgraph):\n    pass\n")

    result = tools.execute_mutation_file(path=write["path"], validate=True)

    assert result["ok"] is False
    assert result["issues"][0]["details"]["issue_kind"] == "logical.topology.direct.missing_edge"


def test_state_changing_tools_close_after_successful_apply(tmp_path):
    artifact = {"graph": _seed_logical_graph_dict(), "constraint_files": {}, "checkpoint_files": {}}
    tools = StageRepairTools(artifact, support_file_root=str(tmp_path))
    bad = tools.write_mutation_file(content="x = 1\n", path="logical/mutations/attempt_1.py")
    assert tools.execute_mutation_file(path=bad["path"])["ok"] is False

    good = tools.write_mutation_file(
        content="def mutate(tgraph):\n    tgraph.ensure_subnet('SW_DMZ', cidr='10.10.10.0/24')\n",
        path="logical/mutations/attempt_2.py",
    )
    assert tools.execute_mutation_file(path=good["path"])["ok"] is True

    blocked = tools.write_mutation_file(
        content="def mutate(tgraph):\n    pass\n",
        path="logical/mutations/attempt_3.py",
    )
    assert blocked["ok"] is False
    assert blocked["stop"] is True


def test_read_support_file_can_read_agent_docs():
    tools = StageRepairTools({"graph": _seed_logical_graph_dict(), "constraint_files": {}, "checkpoint_files": {}})

    result = tools.read_support_file("docs/tgraph_view_api.md", match="tgraph.nodes")
    legacy = tools.read_support_file("tgraph_view_api.md", match="tgraph.nodes")
    files = tools.list_support_files()

    assert result["ok"] is True
    assert result["path"] == "docs/tgraph_view_api.md"
    assert "tgraph.nodes" in result["content"]
    assert legacy["ok"] is True
    assert "docs/tgraph_view_api.md" in files["agent_docs"]


def test_inspect_graph_node_view_requires_node_id():
    tools = StageRepairTools({"graph": _seed_logical_graph_dict(), "constraint_files": {}, "checkpoint_files": {}})
    result = tools.inspect_graph(view="node")
    assert result["ok"] is False
    assert "node_id" in result["error"]["message"]


def test_inspect_graph_path_view_requires_endpoints():
    tools = StageRepairTools({"graph": _seed_logical_graph_dict(), "constraint_files": {}, "checkpoint_files": {}})
    result = tools.inspect_graph(view="path", source="A")
    assert result["ok"] is False
    assert "source and target" in result["error"]["message"]


def test_inspect_graph_unknown_view_returns_error_instead_of_raising():
    tools = StageRepairTools({"graph": _seed_logical_graph_dict(), "constraint_files": {}, "checkpoint_files": {}})

    result = tools.inspect_graph(view="wat")

    assert result["ok"] is False
    assert "allowed_views" in result


def test_inspect_graph_nodes_view_lists_compact_nodes():
    tools = StageRepairTools({"graph": _seed_logical_graph_dict(), "constraint_files": {}, "checkpoint_files": {}})

    result = tools.inspect_graph(view="nodes")

    assert result["ok"] is True
    assert result["nodes"] == [{"id": "SW_DMZ", "type": "switch", "label": "SW_DMZ", "port_count": 0}]
