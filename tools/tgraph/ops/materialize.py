from __future__ import annotations

from typing import Any

from tools.tgraph.model import Node, TGraph, ensure_tgraph
from tools.tgraph.model.link import Link
from tools.tgraph.model.profiles import TAAL_DEFAULT_V1


def materialize(
    graph: TGraph | dict[str, Any],
    target_profile: str = TAAL_DEFAULT_V1,
    defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    model = ensure_tgraph(graph)
    defaults = defaults or {}
    indexes = model.build_indexes()
    nodes = [_materialize_node(node, defaults) for node in model.nodes]
    links = [_materialize_link(link, indexes.port_owner) for link in model.links]

    materialized = TGraph(profile=target_profile, nodes=nodes, links=links)
    return materialized.model_dump(mode="json")


def _materialize_node(node: Node, defaults: dict[str, Any]) -> Node:
    if node.type == "computer":
        computer_defaults = defaults.get("computer", {})
        image = node.image.model_dump(mode="json") if node.image is not None else computer_defaults.get("image")
        flavor = node.flavor.model_dump(mode="json") if node.flavor is not None else computer_defaults.get("flavor")
        if image is None:
            raise ValueError(f"materialize_missing_image_mapping:{node.id}")
        if flavor is None:
            raise ValueError(f"materialize_missing_flavor_mapping:{node.id}")
        return Node.model_validate(
            {
                "id": node.id,
                "type": node.type,
                "label": node.label,
                "ports": [port.model_dump(mode="json") for port in node.ports],
                "image": image,
                "flavor": flavor,
            }
        )

    return Node.model_validate(
        {
            "id": node.id,
            "type": node.type,
            "label": node.label,
            "ports": [port.model_dump(mode="json") for port in node.ports],
            "image": None,
            "flavor": None,
        }
    )


def _materialize_link(link: Link, port_owner: dict[str, str]) -> Link:
    from_node = link.from_node or port_owner.get(link.from_port)
    to_node = link.to_node or port_owner.get(link.to_port)
    if from_node is None:
        raise ValueError(f"materialize_port_owner_not_found:{link.from_port}")
    if to_node is None:
        raise ValueError(f"materialize_port_owner_not_found:{link.to_port}")

    return Link(
        id=link.id,
        from_port=link.from_port,
        to_port=link.to_port,
        from_node=from_node,
        to_node=to_node,
    )
