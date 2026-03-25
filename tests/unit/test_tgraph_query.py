import pytest

from tools.tgraph.query.graph import connected_components
from tools.tgraph.query.link import get_link, list_links
from tools.tgraph.query.node import list_nodes
from tools.tgraph.query.port import owner_of


def test_owner_of_returns_the_port_owner() -> None:
    graph = {
        "profile": "taal.default.v1",
        "nodes": [
            {"id": "R1", "type": "router", "label": "R1", "ports": [{"id": "R1:p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            {"id": "PC1", "type": "computer", "label": "PC1", "ports": [{"id": "PC1:p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": {"id": "img", "name": "img"}, "flavor": {"vcpu": 1, "ram": 512, "disk": 10}},
            {"id": "R2", "type": "router", "label": "R2", "ports": [], "image": None, "flavor": None},
        ],
        "links": [{"id": "R1:p1--PC1:p1", "from_port": "R1:p1", "to_port": "PC1:p1", "from_node": "R1", "to_node": "PC1"}],
    }

    assert owner_of(graph, "R1:p1") == "R1"


def test_connected_components_groups_nodes_by_links() -> None:
    graph = {
        "profile": "taal.default.v1",
        "nodes": [
            {"id": "R1", "type": "router", "label": "R1", "ports": [{"id": "R1:p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            {"id": "PC1", "type": "computer", "label": "PC1", "ports": [{"id": "PC1:p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": {"id": "img", "name": "img"}, "flavor": {"vcpu": 1, "ram": 512, "disk": 10}},
            {"id": "R2", "type": "router", "label": "R2", "ports": [], "image": None, "flavor": None},
        ],
        "links": [{"id": "R1:p1--PC1:p1", "from_port": "R1:p1", "to_port": "PC1:p1", "from_node": "R1", "to_node": "PC1"}],
    }

    groups = connected_components(graph)

    assert groups == [{"PC1", "R1"}, {"R2"}]


def test_get_link_returns_the_exact_link() -> None:
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [{"id": "PLC1:eth0", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            {"id": "SW1", "type": "switch", "label": "SW1", "ports": [{"id": "SW1:ge0/1", "ip": "", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
        ],
        "links": [{"id": "PLC1:eth0--SW1:ge0/1", "from_port": "PLC1:eth0", "to_port": "SW1:ge0/1", "from_node": "PLC1", "to_node": "SW1"}],
    }

    link = get_link(graph, "PLC1:eth0--SW1:ge0/1")

    assert link.id == "PLC1:eth0--SW1:ge0/1"
    assert link.from_port == "PLC1:eth0"
    assert link.to_port == "SW1:ge0/1"


def test_list_links_supports_node_and_port_filters() -> None:
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [{"id": "PLC1:eth0", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            {"id": "SW1", "type": "switch", "label": "SW1", "ports": [{"id": "SW1:ge0/1", "ip": "", "cidr": "10.0.0.0/24"}, {"id": "SW1:ge0/2", "ip": "", "cidr": "10.0.1.0/24"}], "image": None, "flavor": None},
            {"id": "HMI1", "type": "computer", "label": "HMI1", "ports": [{"id": "HMI1:eth0", "ip": "10.0.1.2", "cidr": "10.0.1.0/24"}], "image": None, "flavor": None},
        ],
        "links": [
            {"id": "PLC1:eth0--SW1:ge0/1", "from_port": "PLC1:eth0", "to_port": "SW1:ge0/1", "from_node": "PLC1", "to_node": "SW1"},
            {"id": "HMI1:eth0--SW1:ge0/2", "from_port": "HMI1:eth0", "to_port": "SW1:ge0/2", "from_node": "HMI1", "to_node": "SW1"},
        ],
    }

    node_links = list_links(graph, node_id="SW1")
    port_links = list_links(graph, port_id="SW1:ge0/2")

    assert {link.id for link in node_links} == {"PLC1:eth0--SW1:ge0/1", "HMI1:eth0--SW1:ge0/2"}
    assert [link.id for link in port_links] == ["HMI1:eth0--SW1:ge0/2"]


def test_get_link_raises_stable_code_when_missing() -> None:
    with pytest.raises(KeyError, match="query_link_not_found:missing"):
        get_link({"profile": "logical.v1", "nodes": [], "links": []}, "missing")


def test_list_nodes_filters_by_type() -> None:
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [], "image": None, "flavor": None},
            {"id": "SW1", "type": "switch", "label": "SW1", "ports": [], "image": None, "flavor": None},
        ],
        "links": [],
    }

    nodes = list_nodes(graph, type="computer")

    assert [node.id for node in nodes] == ["PLC1"]
