from tgraph import TGraph


def test_patch_schema_rejects_unknown_operations():
    from tgraph.operations.patch import TGraphPatch

    result = TGraphPatch.from_json({"graph_patch": [{"op": "dance"}]})

    assert result.ok is False
    assert result.error == {"code": "patch_schema_error", "message": "unknown graph op: dance"}


def test_apply_patch_ensure_node_creates_and_merges():
    from tgraph import apply_patch

    graph = TGraph.model_validate({"stage": "logical", "nodes": [], "links": []})

    created = apply_patch(
        graph,
        {"graph_patch": [{"op": "ensure_node", "id": "R1", "type": "router", "label": "Router"}]},
        validate=False,
        include_graph=True,
    )
    merged = apply_patch(
        created.graph,
        {"graph_patch": [{"op": "ensure_node", "id": "R1", "label": "Core Router"}]},
        validate=False,
        include_graph=True,
    )

    assert created.ok is True
    assert created.diff["nodes_added"] == ["R1"]
    assert merged.graph.nodes[0].label == "Core Router"
    assert merged.diff["nodes_updated"] == ["R1"]


def test_apply_patch_ensure_port_and_link_creates_topology():
    from tgraph import apply_patch

    graph = TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {"id": "R1", "type": "router", "label": "R1"},
                {"id": "SW1", "type": "switch", "label": "SW1"},
            ],
            "links": [],
        }
    )

    result = apply_patch(
        graph,
        {
            "graph_patch": [
                {"op": "ensure_port", "node": "R1", "port": "r1p1", "ip": "10.0.0.1"},
                {
                    "op": "ensure_link",
                    "a": {"node": "R1", "port": "r1p1"},
                    "b": {"node": "SW1", "port": "sw1p1", "cidr": "10.0.0.0/24"},
                },
            ]
        },
        validate=True,
        include_graph=True,
    )

    assert result.ok is True
    assert result.graph.links[0].id == "r1p1--sw1p1"
    assert result.diff["ports_added"] == ["R1.r1p1", "SW1.sw1p1"]
    assert result.validation.ok is True


def test_apply_patch_rejects_connected_port_without_reconnect_and_preserves_original():
    from tgraph import apply_patch

    graph = TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {"id": "A", "type": "router", "label": "A", "ports": [{"id": "a1"}]},
                {"id": "B", "type": "computer", "label": "B", "ports": [{"id": "b1"}]},
                {"id": "C", "type": "computer", "label": "C", "ports": [{"id": "c1"}]},
            ],
            "links": [{"id": "a1--b1", "from_port": "a1", "to_port": "b1"}],
        }
    )

    result = apply_patch(
        graph,
        {"graph_patch": [{"op": "ensure_link", "a": {"port": "a1"}, "b": {"port": "c1"}}]},
        validate=False,
        include_graph=True,
    )

    assert result.ok is False
    assert result.error["code"] == "patch_conflict"
    assert graph.links[0].id == "a1--b1"
    assert result.graph is None


def test_apply_patch_remove_node_cascade_and_set_stage():
    from tgraph import apply_patch

    graph = TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {"id": "A", "type": "router", "label": "A", "ports": [{"id": "a1"}]},
                {"id": "B", "type": "computer", "label": "B", "ports": [{"id": "b1"}]},
            ],
            "links": [{"id": "a1--b1", "from_port": "a1", "to_port": "b1"}],
        }
    )

    result = apply_patch(
        graph,
        {"graph_patch": [{"op": "remove_node", "id": "B", "cascade": True}, {"op": "set_stage", "stage": "physical"}]},
        validate=False,
        include_graph=True,
    )

    assert result.ok is True
    assert result.graph.stage == "physical"
    assert [node.id for node in result.graph.nodes] == ["A"]
    assert result.graph.links == []
    assert result.diff["nodes_removed"] == ["B"]
    assert result.diff["links_removed"] == ["a1--b1"]

