from typing import Any

from pydantic import BaseModel, Field


class CheckpointSpec(BaseModel):
    id: str
    function_name: str
    input_params: dict[str, Any] = Field(default_factory=dict)
    description: str
    script_ref: str | None = None


class LogicalRoundOutput(BaseModel):
    logical_checkpoints: list[CheckpointSpec] = Field(default_factory=list)
    logical_patch_ops: list[dict[str, Any]] = Field(default_factory=list)
    logical_validator_script: str | None = None
    tgraph_logical: dict[str, Any] = Field(default_factory=dict)


class PhysicalRoundOutput(BaseModel):
    physical_checkpoints: list[CheckpointSpec] = Field(default_factory=list)
    physical_patch_ops: list[dict[str, Any]] = Field(default_factory=list)
    physical_validator_script: str | None = None
    tgraph_physical: dict[str, Any] = Field(default_factory=dict)
