from tools.tgraph.validate.f3_consistency import f3_consistency


def test_f3_reports_duplicate_port_ids() -> None:
    issues = f3_consistency(
        {
            "profile": "logical.v1",
            "nodes": [
                {
                    "id": "R1",
                    "type": "router",
                    "label": "R1",
                    "ports": [{"id": "p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}],
                    "image": None,
                    "flavor": None,
                },
                {
                    "id": "R2",
                    "type": "router",
                    "label": "R2",
                    "ports": [{"id": "p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}],
                    "image": None,
                    "flavor": None,
                },
            ],
            "links": [],
        }
    )

    assert issues[0]["code"] == "duplicate_port_id"


def test_f3_reports_link_id_mismatch() -> None:
    issues = f3_consistency(
        {
            "profile": "logical.v1",
            "nodes": [
                {
                    "id": "A",
                    "type": "router",
                    "label": "A",
                    "ports": [{"id": "A:p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}],
                    "image": None,
                    "flavor": None,
                },
                {
                    "id": "B",
                    "type": "router",
                    "label": "B",
                    "ports": [{"id": "B:p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}],
                    "image": None,
                    "flavor": None,
                },
            ],
            "links": [{"id": "wrong", "from_port": "A:p1", "to_port": "B:p1", "from_node": "A", "to_node": "B"}],
        }
    )

    assert issues[0]["code"] == "link_id_mismatch"


def test_f3_rejects_port_linked_more_than_once() -> None:
    issues = f3_consistency(
        {
            "profile": "logical.v1",
            "nodes": [
                {
                    "id": "PLC1",
                    "type": "computer",
                    "label": "PLC1",
                    "ports": [{"id": "PLC1:eth0", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}],
                    "image": None,
                    "flavor": None,
                },
                {
                    "id": "SW1",
                    "type": "switch",
                    "label": "SW1",
                    "ports": [{"id": "SW1:ge0/1", "ip": "", "cidr": "10.0.0.0/24"}],
                    "image": None,
                    "flavor": None,
                },
                {
                    "id": "RTR1",
                    "type": "router",
                    "label": "RTR1",
                    "ports": [{"id": "RTR1:ge0/0", "ip": "10.0.1.1", "cidr": "10.0.1.0/24"}],
                    "image": None,
                    "flavor": None,
                },
            ],
            "links": [
                {"id": "PLC1:eth0--SW1:ge0/1", "from_port": "PLC1:eth0", "to_port": "SW1:ge0/1", "from_node": "PLC1", "to_node": "SW1"},
                {"id": "PLC1:eth0--RTR1:ge0/0", "from_port": "PLC1:eth0", "to_port": "RTR1:ge0/0", "from_node": "PLC1", "to_node": "RTR1"},
            ],
        }
    )

    assert {issue["code"] for issue in issues} >= {"port_degree_exceeded"}
