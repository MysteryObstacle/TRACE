from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tgraph import TGraph


class StageAuthorArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checkpoint_files: dict[str, str] = Field(default_factory=dict)


class LogicalAuthorArtifact(StageAuthorArtifact):
    pass


class PhysicalAuthorArtifact(StageAuthorArtifact):
    pass


class StageArtifact(StageAuthorArtifact):
    model_config = ConfigDict(extra="forbid")

    graph: TGraph
    constraint_files: dict[str, str] = Field(default_factory=dict)


class LogicalArtifact(StageArtifact):
    @model_validator(mode="after")
    def _ensure_logical_stage(self) -> "LogicalArtifact":
        if self.graph.stage != "logical":
            raise ValueError("logical artifact graph must use stage='logical'")
        return self


class PhysicalArtifact(StageArtifact):
    @model_validator(mode="after")
    def _ensure_physical_stage(self) -> "PhysicalArtifact":
        if self.graph.stage != "physical":
            raise ValueError("physical artifact graph must use stage='physical'")
        return self
