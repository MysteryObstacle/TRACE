from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from tools.tgraph.model.port import Port


class ImageSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str


class FlavorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vcpu: int
    ram: int
    disk: int


class Node(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["switch", "router", "computer"]
    label: str
    ports: list[Port] = Field(default_factory=list)
    image: ImageSpec | None = None
    flavor: FlavorSpec | None = None
