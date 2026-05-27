from tgraph import TGraph, init_logical_skeleton, init_physical_skeleton


def test_init_logical_skeleton_expands_node_groups_to_nodes_only() -> None:
    graph = init_logical_skeleton(
        [
            {"type": "computer", "members": ["PLC[1..2]"]},
            {"type": "switch", "members": ["SW_OT"]},
        ]
    )

    assert graph.stage == "logical"
    assert [(node.id, node.type) for node in graph.nodes] == [
        ("PLC1", "computer"),
        ("PLC2", "computer"),
        ("SW_OT", "switch"),
    ]
    assert all(node.ports == [] for node in graph.nodes)
    assert graph.links == []


def test_init_physical_skeleton_copies_topology_and_applies_node_type_defaults() -> None:
    logical = TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {"id": "R_CORE", "type": "router", "label": "R_CORE", "ports": [{"id": "_SW-1"}]},
                {"id": "SW", "type": "switch", "label": "SW", "ports": [{"id": "_R_CORE-1"}]},
                {
                    "id": "WEB",
                    "type": "computer",
                    "label": "WEB",
                    "image": {"id": "custom-web", "name": "Custom Web"},
                    "ports": [],
                },
            ],
            "links": [{"id": "R_CORE-SW-1", "from_node": "R_CORE", "from_port": "_SW-1", "to_node": "SW", "to_port": "_R_CORE-1"}],
        }
    )

    physical = init_physical_skeleton(
        logical,
        defaults_by_type={
            "computer": {
                "image": {"id": "ubuntu", "name": "Ubuntu"},
                "flavor": {"vcpu": 2, "ram": 4096, "disk": 40},
            },
            "router": {
                "image": {"id": "vyos", "name": "VyOS"},
                "flavor": {"vcpu": 1, "ram": 1024, "disk": 10},
            },
            "switch": {"image": None, "flavor": None},
        },
    )

    assert physical.stage == "physical"
    assert [link.id for link in physical.links] == ["R_CORE-SW-1"]
    router = next(node for node in physical.nodes if node.id == "R_CORE")
    switch = next(node for node in physical.nodes if node.id == "SW")
    web = next(node for node in physical.nodes if node.id == "WEB")
    assert router.image.id == "vyos"
    assert router.flavor.vcpu == 1
    assert switch.image is None
    assert switch.flavor is None
    assert web.image.id == "custom-web"
    assert web.flavor.vcpu == 2
