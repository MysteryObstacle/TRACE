from tgraph import TGraph
from tgraph.operations.validate.view import TGraphView


def _graph() -> TGraph:
    return TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {"id": "WEB", "type": "computer", "label": "WEB", "ports": [{"id": "_SW_DMZ-1", "cidr": "10.10.10.0/24"}]},
                {
                    "id": "SW_DMZ",
                    "type": "switch",
                    "label": "SW_DMZ",
                    "ports": [
                        {"id": "_WEB-1", "cidr": "10.10.10.0/24"},
                        {"id": "_R_CORE-1", "cidr": "10.10.10.0/24"},
                    ],
                },
                {"id": "R_CORE", "type": "router", "label": "R_CORE", "ports": [{"id": "_SW_DMZ-1", "ip": "10.10.10.1", "cidr": "10.10.10.0/24"}]},
                {"id": "PLC1", "type": "computer", "label": "PLC1", "ports": []},
                {"id": "FW1", "type": "router", "label": "FW1", "ports": []},
            ],
            "links": [
                {"id": "SW_DMZ-WEB-1", "from_node": "WEB", "from_port": "_SW_DMZ-1", "to_node": "SW_DMZ", "to_port": "_WEB-1"},
                {"id": "R_CORE-SW_DMZ-1", "from_node": "R_CORE", "from_port": "_SW_DMZ-1", "to_node": "SW_DMZ", "to_port": "_R_CORE-1"},
            ],
        }
    )


def test_check_subnet_requires_all_switch_ports_in_cidr() -> None:
    view = TGraphView(_graph())

    assert view.check_subnet("SW_DMZ", "10.10.10.0/24") == []

    issues = view.check_subnet("SW_DMZ", "10.10.20.0/24")
    assert _issue_kinds(issues) == ["logical.addressing.subnet.cidr_mismatch"]
    assert issues[0]["details"]["fact_kind"] == "logical.addressing.subnet"
    assert issues[0]["details"]["repair_target"] == "graph"
    assert issues[0]["details"]["expected_cidr"] == "10.10.20.0/24"


def test_check_interface_requires_direct_link_and_endpoint_addressing() -> None:
    view = TGraphView(_graph())

    assert view.check_interface("R_CORE", segment="SW_DMZ", ip="10.10.10.1", cidr="10.10.10.0/24") == []

    issues = view.check_interface("PLC1", segment="SW_DMZ", cidr="10.10.30.0/24")
    assert _issue_kinds(issues) == ["logical.addressing.interface.missing_link"]
    assert issues[0]["details"]["expected_edge"] == ["PLC1", "SW_DMZ"]


def test_check_direct_chain_ring_star_and_mesh_topologies() -> None:
    view = TGraphView(_graph())

    assert view.check_direct_link("WEB", "SW_DMZ") == []
    assert view.check_chain(["WEB", "SW_DMZ", "R_CORE"]) == []

    missing_chain = view.check_chain(["WEB", "SW_DMZ", "PLC1"])
    assert _issue_kinds(missing_chain) == ["logical.topology.chain.missing_edge"]
    assert missing_chain[0]["details"]["expected_edge"] == ["SW_DMZ", "PLC1"]

    missing_ring = view.check_ring(["WEB", "SW_DMZ", "R_CORE"])
    assert _issue_kinds(missing_ring) == ["logical.topology.ring.missing_edge"]

    missing_star = view.check_star(center="SW_DMZ", leaves=["WEB", "R_CORE", "PLC1"])
    assert _issue_kinds(missing_star) == ["logical.topology.star.missing_edge"]

    missing_mesh = view.check_mesh(["WEB", "SW_DMZ", "R_CORE"])
    assert _issue_kinds(missing_mesh) == ["logical.topology.mesh.missing_edge"]


def _issue_kinds(issues):
    return [issue["details"]["issue_kind"] for issue in issues]
