from typing import Any

from pydantic import BaseModel, Field

from stages.logical.output_schema import CheckpointSpec


class PhysicalOutput(BaseModel):
    physical_checkpoints: list[CheckpointSpec] = Field(default_factory=list)
    tgraph_physical: dict[str, Any] = Field(default_factory=dict)
    physical_validator_script: str | None = None
