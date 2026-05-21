from __future__ import annotations

from pydantic import BaseModel, Field

from trace.stages.common import CheckpointSpec
from trace.tools.tgraph.model import TGraphJSON


class PhysicalAuthorArtifact(BaseModel):
    physical_checkpoints: list[CheckpointSpec] = Field(default_factory=list)
    physical_validator_script: str | None = None


class PhysicalArtifact(BaseModel):
    physical_checkpoints: list[CheckpointSpec] = Field(default_factory=list)
    physical_validator_script: str | None = None
    tgraph_physical: TGraphJSON
