from tools.tgraph.ops.materialize import materialize


def test_materialize_promotes_logical_graph_to_taal_profile() -> None:
    logical = {
        "profile": "logical.v1",
        "nodes": [
            {
                "id": "PC1",
                "type": "computer",
                "label": "PC1",
                "ports": [{"id": "PC1:p1", "ip": "10.0.0.10", "cidr": "10.0.0.0/24"}],
                "image": None,
                "flavor": None,
            }
        ],
        "links": [],
    }

    physical = materialize(
        logical,
        target_profile="taal.default.v1",
        defaults={
            "computer": {
                "image": {"id": "ubuntu-22", "name": "Ubuntu 22.04"},
                "flavor": {"vcpu": 2, "ram": 2048, "disk": 20},
            }
        },
    )

    assert physical["profile"] == "taal.default.v1"
    assert physical["nodes"][0]["image"]["id"] == "ubuntu-22"
