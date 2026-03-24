from typing import Literal

from pydantic import BaseModel, Field


class ConstraintItem(BaseModel):
    id: str
    scope: Literal["node_ids", "topology"]
    text: str


class GroundOutput(BaseModel):
    node_patterns: list[str] = Field(default_factory=list)
    logical_constraints: list[ConstraintItem] = Field(default_factory=list)
    physical_constraints: list[ConstraintItem] = Field(default_factory=list)
