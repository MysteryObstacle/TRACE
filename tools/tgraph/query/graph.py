from __future__ import annotations

import networkx as nx

from tools.tgraph.graph_view import to_networkx
from tools.tgraph.model import TGraph, ensure_tgraph


def connected_components(graph: TGraph | dict) -> list[set[str]]:
    model = ensure_tgraph(graph)
    view = to_networkx(model)
    return [set(component) for component in nx.connected_components(view)]
