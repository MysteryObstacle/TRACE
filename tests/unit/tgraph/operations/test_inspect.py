from tgraph import TGraph


def _graph() -> TGraph:
    return TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {"id": "R1", "type": "router", "label": "Router", "ports": [{"id": "r1p1", "ip": "10.0.0.1"}]},
                {
                    "id": "SW1",
                    "type": "switch",
                    "label": "Switch",
                    "ports": [
                        {"id": "sw1p1", "cidr": "10.0.0.0/24"},
                        {"id": "sw1p2", "cidr": "10.0.0.0/24"},
                    ],
                },
                {"id": "APP", "type": "computer", "label": "App", "ports": [{"id": "appp1", "ip": "10.0.0.10"}]},
            ],
            "links": [
                {"id": "r1p1--sw1p1", "from_port": "r1p1", "to_port": "sw1p1", "from_node": "R1", "to_node": "SW1"},
                {"id": "appp1--sw1p2", "from_port": "appp1", "to_port": "sw1p2", "from_node": "APP", "to_node": "SW1"},
            ],
        }
    )


def test_inspect_summary_returns_counts_by_type():
    from tgraph import inspect_graph

    result = inspect_graph(_graph(), view="summary")

    assert result == {
        "stage": "logical",
        "node_count": 3,
        "link_count": 2,
        "node_types": {"computer": 1, "router": 1, "switch": 1},
    }


def test_inspect_node_returns_focused_node_or_none():
    from tgraph import inspect_graph

    found = inspect_graph(_graph(), view="node", node_id="R1")
    missing = inspect_graph(_graph(), view="node", node_id="NOPE")

    assert found["node"]["id"] == "R1"
    assert missing == {"node": None}


def test_inspect_links_filters_by_node_or_port():
    from tgraph import inspect_graph

    by_node = inspect_graph(_graph(), view="links", node_id="SW1")
    by_port = inspect_graph(_graph(), view="links", port_id="r1p1")

    assert [link["id"] for link in by_node["links"]] == ["r1p1--sw1p1", "appp1--sw1p2"]
    assert [link["id"] for link in by_port["links"]] == ["r1p1--sw1p1"]


def test_inspect_path_returns_reachable_node_path():
    from tgraph import inspect_graph

    result = inspect_graph(_graph(), view="path", source="R1", target="APP")

    assert result == {"reachable": True, "path": ["R1", "SW1", "APP"]}


def test_inspect_segments_groups_ports_by_cidr():
    from tgraph import inspect_graph

    result = inspect_graph(_graph(), view="segments")

    assert result == {
        "segments": [
            {
                "cidr": "10.0.0.0/24",
                "ports": [
                    {"node": "SW1", "port": "sw1p1"},
                    {"node": "SW1", "port": "sw1p2"},
                ],
            }
        ]
    }

