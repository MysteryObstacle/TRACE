from trace.stages.repair_tools import MutationSummary, StageRepairTools, _derive_op_counts


def test_derive_op_counts_aggregates_by_op_name():
    operations = [
        {"op": "ensure_direct_link", "link": "A-B-1", "nodes": ["A", "B"], "link_key": "1"},
        {"op": "ensure_direct_link", "link": "B-C-1", "nodes": ["B", "C"], "link_key": "1"},
        {"op": "set_image", "node": "A", "image_id": "img_pfsense"},
    ]
    assert _derive_op_counts(operations) == {"ensure_direct_link": 2, "set_image": 1}


def test_mutation_summary_affected_node_ids_from_scalar_and_list_fields():
    operations = [
        {"op": "ensure_node", "node": "A"},
        {"op": "ensure_direct_link", "link": "A-B-1", "nodes": ["A", "B"]},
        {"op": "set_image", "node": "B", "image_id": "img_pfsense"},
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
