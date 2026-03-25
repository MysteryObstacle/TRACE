from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tools.tgraph.model.indexes import TGraphIndexes, build_indexes
from tools.tgraph.model.link import Link
from tools.tgraph.model.node import Node


class TGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: str
    nodes: list[Node] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_edges_to_links(cls, value: Any) -> Any:
        if isinstance(value, dict) and "edges" in value and "links" not in value:
            payload = dict(value)
            payload["links"] = payload.pop("edges")
            return payload
        return value

    def build_indexes(self) -> TGraphIndexes:
        return build_indexes(self)


def ensure_tgraph(graph: TGraph | dict[str, Any]) -> TGraph:
    if isinstance(graph, TGraph):
        return graph
    if isinstance(graph, dict):
        return TGraph.model_validate(graph)
    raise TypeError("tgraph must be a TGraph or dict payload")
