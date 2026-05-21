from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from tgraph.core.graph import TGraph
from tgraph.core.stage import GraphStage

ValidationLevel = Literal["f1", "f2", "f3", "f4"]


class ValidationPolicy(BaseModel):
    levels: list[ValidationLevel] = Field(default_factory=lambda: ["f1", "f2", "f3", "f4"])
    stage: GraphStage | None = None


class ValidationContext(BaseModel):
    preserve_topology_from: TGraph | None = None
    required_node_fields: list[str] = Field(default_factory=list)
    required_link_fields: list[str] = Field(default_factory=list)
    checkpoints: list[dict[str, Any]] = Field(default_factory=list)

