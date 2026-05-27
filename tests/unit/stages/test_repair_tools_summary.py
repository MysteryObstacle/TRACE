from trace.stages.repair_tools import MutationSummary, _derive_op_counts


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
