from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


LOGICAL_V1 = "logical.v1"
TAAL_DEFAULT_V1 = "taal.default.v1"
SUPPORTED_PROFILES = {LOGICAL_V1, TAAL_DEFAULT_V1}


class ImageSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str


class FlavorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vcpu: int
    ram: int
    disk: int


class Port(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    ip: str = ""
    cidr: str = ""


class Node(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["switch", "router", "computer"]
    label: str
    ports: list[Port] = Field(default_factory=list)
    image: ImageSpec | None = None
    flavor: FlavorSpec | None = None


class Link(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    from_port: str
    to_port: str
    from_node: str | None = None
    to_node: str | None = None


class TGraphJSON(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: str
    nodes: list[Node] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)

def ensure_tgraph_json(graph: TGraphJSON | dict[str, Any]) -> TGraphJSON:
    if isinstance(graph, TGraphJSON):
        return graph
    return TGraphJSON.model_validate(graph)


def normalize_tgraph_json(graph: TGraphJSON | dict[str, Any]) -> TGraphJSON:
    from trace.tools.tgraph.runtime import TGraphRuntime

    return TGraphJSON.model_validate(TGraphRuntime.from_json(graph).to_json())
