import pytest

from tgraph import TGraph
from tgraph.operations.mutate import TGraphEditor


def _graph() -> TGraph:
    return TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {"id": "WEB", "type": "computer", "label": "WEB"},
                {"id": "SW_DMZ", "type": "switch", "label": "SW_DMZ"},
                {"id": "R_CORE", "type": "router", "label": "R_CORE"},
                {"id": "PLC1", "type": "computer", "label": "PLC1"},
            ],
            "links": [],
        }
    )


def test_ensure_direct_link_creates_stable_node_scoped_ports_and_link() -> None:
    editor = TGraphEditor(_graph())

    editor.ensure_direct_link("WEB", "SW_DMZ")
    editor.ensure_direct_link("WEB", "SW_DMZ")
    graph = editor.to_graph()

    assert graph.links[0].id == "SW_DMZ-WEB-1"
    assert graph.links[0].from_node == "WEB"
    assert graph.links[0].from_port == "_SW_DMZ-1"
    assert graph.links[0].to_node == "SW_DMZ"
    assert graph.links[0].to_port == "_WEB-1"
    web = next(node for node in graph.nodes if node.id == "WEB")
    assert [port.id for port in web.ports] == ["_SW_DMZ-1"]
    assert [item["op"] for item in editor.operations] == ["ensure_direct_link"]


def test_ensure_direct_link_supports_parallel_semantic_keys() -> None:
    editor = TGraphEditor(_graph())

    editor.ensure_direct_link("R_CORE", "SW_DMZ", link_key="primary")
    editor.ensure_direct_link("R_CORE", "SW_DMZ", link_key="backup")
    graph = editor.to_graph()

    assert [link.id for link in graph.links] == ["R_CORE-SW_DMZ-backup", "R_CORE-SW_DMZ-primary"]
    r_core = next(node for node in graph.nodes if node.id == "R_CORE")
    assert [port.id for port in r_core.ports] == ["_SW_DMZ-1", "_SW_DMZ-2"]


def test_topology_helpers_create_chain_ring_star_and_mesh() -> None:
    editor = TGraphEditor(_graph())

    editor.ensure_chain(["WEB", "SW_DMZ", "R_CORE"])
    editor.ensure_ring(["WEB", "SW_DMZ", "R_CORE"])
    editor.ensure_star(center="SW_DMZ", leaves=["WEB", "R_CORE", "PLC1"])
    editor.ensure_mesh(["WEB", "SW_DMZ", "R_CORE"])
    graph = editor.to_graph()

    assert {link.id for link in graph.links} == {
        "R_CORE-SW_DMZ-1",
        "SW_DMZ-WEB-1",
        "R_CORE-WEB-1",
        "PLC1-SW_DMZ-1",
    }


def test_ensure_subnet_and_interface_set_both_endpoint_cidrs() -> None:
    editor = TGraphEditor(_graph())

    editor.ensure_interface("R_CORE", segment="SW_DMZ", ip="10.10.10.1", cidr="10.10.10.0/24")
    editor.ensure_interface("WEB", segment="SW_DMZ", cidr="10.10.10.0/24")
    editor.ensure_subnet("SW_DMZ", cidr="10.10.10.0/24")
    graph = editor.to_graph()

    r_core = next(node for node in graph.nodes if node.id == "R_CORE")
    sw_dmz = next(node for node in graph.nodes if node.id == "SW_DMZ")
    assert r_core.ports[0].ip == "10.10.10.1"
    assert {port.cidr for port in r_core.ports} == {"10.10.10.0/24"}
    assert {port.cidr for port in sw_dmz.ports} == {"10.10.10.0/24"}


def test_remove_direct_link_removes_only_target_link_and_unused_endpoint_ports() -> None:
    editor = TGraphEditor(_graph())
    editor.ensure_direct_link("R_CORE", "SW_DMZ", link_key="primary")
    editor.ensure_direct_link("R_CORE", "SW_DMZ", link_key="backup")

    removed = editor.remove_direct_link("R_CORE", "SW_DMZ", link_key="primary")
    graph = editor.to_graph()

    assert removed["links_removed"] == ["R_CORE-SW_DMZ-primary"]
    assert [link.id for link in graph.links] == ["R_CORE-SW_DMZ-backup"]
    r_core = next(node for node in graph.nodes if node.id == "R_CORE")
    assert [port.id for port in r_core.ports] == ["_SW_DMZ-2"]


def test_remove_links_between_is_destructive_and_reports_affected_ids() -> None:
    editor = TGraphEditor(_graph())
    editor.ensure_direct_link("R_CORE", "SW_DMZ", link_key="primary")
    editor.ensure_direct_link("R_CORE", "SW_DMZ", link_key="backup")

    removed = editor.remove_links_between("R_CORE", "SW_DMZ")
    graph = editor.to_graph()

    assert removed["destructive"] is True
    assert removed["links_removed"] == ["R_CORE-SW_DMZ-backup", "R_CORE-SW_DMZ-primary"]
    assert graph.links == []


def test_editor_rejects_invalid_link_key() -> None:
    editor = TGraphEditor(_graph())

    with pytest.raises(ValueError, match="link_key"):
        editor.ensure_direct_link("WEB", "SW_DMZ", link_key="bad-key")
