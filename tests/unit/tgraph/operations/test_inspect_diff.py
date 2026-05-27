from tgraph import TGraph
from tgraph.operations.inspect.diff import diff


def _build(stage, nodes, links=None):
    return TGraph.model_validate({
        "stage": stage,
        "nodes": nodes,
        "links": links or [],
    })


def test_diff_reports_added_nodes():
    baseline = _build("logical", [{"id": "A", "type": "computer", "label": "A", "ports": []}])
    current = _build(
        "logical",
        [
            {"id": "A", "type": "computer", "label": "A", "ports": []},
            {"id": "B", "type": "switch", "label": "B", "ports": []},
        ],
    )
    result = diff(current, baseline)
    assert result["added_nodes"] == ["B"]
    assert result["removed_nodes"] == []
    assert result["changed_nodes"] == []
    assert result["unchanged_count"] == 1


def test_diff_reports_removed_nodes():
    baseline = _build(
        "logical",
        [
            {"id": "A", "type": "computer", "label": "A", "ports": []},
            {"id": "B", "type": "switch", "label": "B", "ports": []},
        ],
    )
    current = _build("logical", [{"id": "A", "type": "computer", "label": "A", "ports": []}])
    result = diff(current, baseline)
    assert result["removed_nodes"] == ["B"]
    assert result["unchanged_count"] == 1


def test_diff_reports_changed_fields():
    baseline = _build(
        "physical",
        [{"id": "FIREWALL", "type": "computer", "label": "FIREWALL", "ports": [], "image": None, "flavor": None}],
    )
    current = _build(
        "physical",
        [
            {
                "id": "FIREWALL",
                "type": "computer",
                "label": "FIREWALL",
                "ports": [],
                "image": {"id": "img_pfsense", "name": "pfsense"},
                "flavor": {"vcpu": 2, "ram": 2048, "disk": 10},
            }
        ],
    )
    result = diff(current, baseline)
    assert result["added_nodes"] == []
    assert result["removed_nodes"] == []
    assert result["changed_nodes"] == [{"id": "FIREWALL", "fields_changed": ["flavor", "image"]}]


def test_diff_ignores_field_order_in_ports():
    baseline = _build(
        "logical",
        [{"id": "A", "type": "computer", "label": "A", "ports": [{"id": "_B-1"}]}],
    )
    current = _build(
        "logical",
        [{"id": "A", "type": "computer", "label": "A", "ports": [{"id": "_B-1"}]}],
    )
    result = diff(current, baseline)
    assert result["unchanged_count"] == 1
    assert result["changed_nodes"] == []
