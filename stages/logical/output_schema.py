from typing import Any

from pydantic import BaseModel, Field


class CheckpointSpec(BaseModel):
    id: str
    function_name: str
    input_params: dict[str, Any] = Field(default_factory=dict)
    description: str
    script_ref: str | None = None


class LogicalOutput(BaseModel):
    logical_checkpoints: list[CheckpointSpec] = Field(default_factory=list)
    tgraph_logical: dict[str, Any] = Field(default_factory=dict)
    logical_validator_script: str | None = None
