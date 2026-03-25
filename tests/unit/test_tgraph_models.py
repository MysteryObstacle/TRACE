from tools.tgraph.model.link import Link
from tools.tgraph.model.node import Node
from tools.tgraph.model.port import Port
from tools.tgraph.model.tgraph import TGraph


def test_tgraph_builds_indexes_for_nodes_ports_and_links() -> None:
    graph = TGraph(
        profile="logical.v1",
        nodes=[
            Node(
                id="R1",
                type="router",
                label="R1",
                ports=[Port(id="R1:p1", ip="10.0.0.1", cidr="10.0.0.0/24")],
                image=None,
                flavor=None,
            ),
            Node(
                id="PC1",
                type="computer",
                label="PC1",
                ports=[Port(id="PC1:p1", ip="10.0.0.2", cidr="10.0.0.0/24")],
                image=None,
                flavor=None,
            ),
        ],
        links=[
            Link(
                id="R1:p1--PC1:p1",
                from_port="R1:p1",
                to_port="PC1:p1",
                from_node="R1",
                to_node="PC1",
            )
        ],
    )

    indexes = graph.build_indexes()

    assert indexes.port_owner["R1:p1"] == "R1"
    assert indexes.link_by_id["R1:p1--PC1:p1"].from_node == "R1"
