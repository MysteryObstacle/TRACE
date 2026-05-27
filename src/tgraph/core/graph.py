from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from tgraph.core.stage import GraphStage

_NODE_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


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

    @field_validator("id")
    @classmethod
    def _validate_node_id(cls, value: str) -> str:
        if not _NODE_ID_RE.match(value):
            raise ValueError("node id must match ^[A-Z][A-Z0-9_]*$ and must not contain '-'")
        return value


class Link(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    from_port: str
    to_port: str
    from_node: str | None = None
    to_node: str | None = None

    @model_validator(mode="after")
    def _require_node_scoped_endpoints(self) -> "Link":
        if not self.from_node or not self.to_node:
            raise ValueError("links must include from_node and to_node endpoint identity")
        return self


class TGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: GraphStage
    nodes: list[Node] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
