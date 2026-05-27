from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from tgraph.core.graph import TGraph
from tgraph.core.stage import GraphStage

ValidationLevel = Literal["f1", "f2", "f3", "f4"]


class ValidationPolicy(BaseModel):
    levels: list[ValidationLevel] = Field(default_factory=lambda: ["f1", "f2", "f3", "f4"])
    stage: GraphStage | None = None


class ValidationContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    preserve_topology_from: TGraph | None = None
    required_node_fields: list[str] = Field(default_factory=list)
    required_link_fields: list[str] = Field(default_factory=list)
    constraint_files: dict[str, str | Path] = Field(default_factory=dict)
    checkpoint_files: dict[str, str | Path] = Field(default_factory=dict)
    checkpoint_timeout_seconds: float = 5.0
    checkpoint_max_processes: int = 1
    references: dict[str, TGraph] = Field(default_factory=dict)
