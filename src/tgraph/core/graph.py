from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from tgraph.core.stage import GraphStage


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


class TGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: GraphStage
    nodes: list[Node] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)

