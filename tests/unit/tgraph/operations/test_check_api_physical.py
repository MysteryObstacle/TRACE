from tgraph import TGraph
from tgraph.operations.validate.view import TGraphView


def _graph() -> TGraph:
    return TGraph.model_validate(
        {
            "stage": "physical",
            "nodes": [
                {
                    "id": "FIREWALL",
                    "type": "computer",
                    "label": "FIREWALL",
                    "image": {"id": "img-fw", "name": "Firewall Appliance"},
                    "flavor": {"vcpu": 4, "ram": 8192, "disk": 80},
                },
                {"id": "WEB", "type": "computer", "label": "WEB"},
            ],
            "links": [],
        }
    )


def test_check_image_exact_accepts_legacy_and_canonical_ids() -> None:
    view = TGraphView(_graph())

    assert view.check_image_exact("FIREWALL", "img-fw") == []
    assert view.check_image_exact("FIREWALL", "pfsense") == []

    issues = view.check_image_exact("FIREWALL", "ubuntu_22")
    assert _issue_kinds(issues) == ["physical.image.exact.mismatch"]
    assert issues[0]["details"]["expected_image_id"] == "ubuntu_22"
    assert issues[0]["details"]["actual_image_id"] == "pfsense"


def test_check_flavor_minimum() -> None:
    view = TGraphView(_graph())

    assert view.check_flavor_minimum("FIREWALL", vcpu=2, ram=4096, disk=40) == []

    issues = view.check_flavor_minimum("FIREWALL", vcpu=8, ram=4096, disk=40)
    assert _issue_kinds(issues) == ["physical.flavor.minimum.too_small"]
    assert issues[0]["details"]["expected_minimum"]["vcpu"] == 8


def test_check_flavor_exact() -> None:
    view = TGraphView(_graph())

    assert view.check_flavor_exact("FIREWALL", vcpu=4, ram=8192, disk=80) == []

    issues = view.check_flavor_exact("WEB", vcpu=2, ram=4096, disk=40)
    assert _issue_kinds(issues) == ["physical.flavor.exact.missing"]
    assert issues[0]["details"]["repair_target"] == "graph"


def _issue_kinds(issues):
    return [issue["details"]["issue_kind"] for issue in issues]
