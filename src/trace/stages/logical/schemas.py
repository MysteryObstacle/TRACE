from __future__ import annotations

from pydantic import BaseModel, Field

from trace.stages.common import CheckpointSpec
from trace.tools.tgraph.model import TGraphJSON


class LogicalAuthorArtifact(BaseModel):
    logical_checkpoints: list[CheckpointSpec] = Field(default_factory=list)
    logical_validator_script: str | None = None


class LogicalArtifact(BaseModel):
    tgraph_logical: TGraphJSON
