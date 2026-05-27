from tgraph import TGraph, inspect_graph


def _graph() -> TGraph:
    return TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {"id": "R1", "type": "router", "label": "Router", "ports": [{"id": "r1p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}]},
                {
                    "id": "SW1",
                    "type": "switch",
                    "label": "Switch",
                    "ports": [
                        {"id": "sw1p1", "cidr": "10.0.0.0/24"},
                        {"id": "sw1p2", "cidr": "10.0.1.0/24"},
                    ],
                },
                {"id": "APP", "type": "computer", "label": "App", "ports": [{"id": "appp1", "ip": "10.0.0.10", "cidr": "10.0.0.0/24"}]},
            ],
            "links": [],
        }
    )


def test_inspect_cidrs_groups_ports_by_cidr() -> None:
    result = inspect_graph(_graph(), view="cidrs")

    assert result == {
        "cidrs": [
            {
                "cidr": "10.0.0.0/24",
                "ports": [
                    {"node": "APP", "port": "appp1"},
                    {"node": "R1", "port": "r1p1"},
                    {"node": "SW1", "port": "sw1p1"},
                ],
            },
            {
                "cidr": "10.0.1.0/24",
                "ports": [{"node": "SW1", "port": "sw1p2"}],
            },
        ]
    }


def test_inspect_exports_cidr_centered_helpers() -> None:
    from tgraph.operations.inspect import list_cidrs, nodes_in_cidr, ports_in_cidr

    assert callable(list_cidrs)
    assert callable(nodes_in_cidr)
    assert callable(ports_in_cidr)


def test_inspect_module_does_not_export_segment_helpers() -> None:
    import tgraph.operations.inspect as inspect_mod

    assert not hasattr(inspect_mod, "segments_for_switch")
    assert not hasattr(inspect_mod, "nodes_on_segment")
