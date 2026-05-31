import json
from pathlib import Path

from tgraph import TGraph, load_tgraph, render_mermaid, write_diagram


def _demo_graph() -> TGraph:
    return TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {"id": "A", "type": "computer", "label": "A", "ports": [{"id": "_B-1"}]},
                {"id": "B", "type": "switch", "label": "B", "ports": [{"id": "_A-1", "cidr": "10.0.0.0/24"}, {"id": "_C-1", "cidr": "10.0.0.0/24"}]},
                {"id": "C", "type": "computer", "label": "C", "ports": [{"id": "_B-1"}]},
                {"id": "R", "type": "router", "label": "R", "ports": [{"id": "_B-1", "cidr": "10.0.0.0/24"}]},
            ],
            "links": [
                {"id": "A-B-1", "from_node": "A", "from_port": "_B-1", "to_node": "B", "to_port": "_A-1"},
                {"id": "B-C-1", "from_node": "C", "from_port": "_B-1", "to_node": "B", "to_port": "_C-1"},
                {"id": "B-R-1", "from_node": "R", "from_port": "_B-1", "to_node": "B", "to_port": "_C-1"},
            ],
        }
    )


def test_render_mermaid_groups_computers_under_switch_subgraph():
    graph = _demo_graph()

    mermaid = render_mermaid(graph)

    assert 'subgraph subnet_B["B (10.0.0.0/24)"]' in mermaid
    assert "A --- B" in mermaid
    assert "C --- B" in mermaid
    assert "R --- B" in mermaid
    assert "class R router" in mermaid
    assert "class B switch" in mermaid
    assert "class A computer" in mermaid


def test_write_diagram_mermaid(tmp_path):
    graph = _demo_graph()
    out = tmp_path / "topology.mmd"

    result = write_diagram(graph, out, format="mermaid")

    assert result.format == "mermaid"
    assert result.mermaid_path == out
    assert out.read_text(encoding="utf-8") == result.mermaid


def test_render_mermaid_from_review_topology_matches_expected_shape():
    topology_path = Path(__file__).resolve().parents[4] / "review-package" / "topology.json"
    graph = load_tgraph(json.loads(topology_path.read_text(encoding="utf-8")))

    mermaid = render_mermaid(graph)

    assert "R_CORE --- SW_DMZ" in mermaid
    assert "FIREWALL --- SW_FW_INET" in mermaid
    assert 'subgraph subnet_SW_OFFICE["SW_OFFICE (10.10.20.0/24)"]' in mermaid
    assert "class FIREWALL computer" in mermaid
