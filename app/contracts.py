from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class StageMode(str, Enum):
    CHECK_AUTHOR = "check_author"
    GRAPH_BUILDER = "graph_builder"
    REPAIR = "repair"


class FailureType(str, Enum):
    CONSTRAINT_PARSE_ERROR = "constraint_parse_error"
    CHECKPOINT_AUTHORING_ERROR = "checkpoint_authoring_error"
    GRAPH_REPAIRABLE_ERROR = "graph_repairable_error"
    STAGE_BOUNDARY_ERROR = "stage_boundary_error"


class ArtifactSelector(BaseModel):
    stage: Literal["runtime", "ground", "logical", "physical"]
    name: str
    required: bool = True


class ArtifactRef(BaseModel):
    stage: Literal["ground", "logical", "physical", "runtime"]
    name: str
    version: int
    path: str
    sha256: str


class StageSpec(BaseModel):
    id: Literal["ground", "logical", "physical"]
    prompt_path: str
    inputs: list[ArtifactSelector] = Field(default_factory=list)
    output_model: str
    allowed_tools: list[str] = Field(default_factory=list)
    max_rounds: int = 1
    repair_mode: Literal["none", "patch"] = "none"


class ValidationIssue(BaseModel):
    code: str
    message: str
    severity: Literal["error", "warning"]
    scope: Literal["topology", "node", "port", "link", "patch", "intent"]
    targets: list[str] = Field(default_factory=list)
    json_paths: list[str] = Field(default_factory=list)

    @field_validator("scope", mode="before")
    @classmethod
    def normalize_scope(cls, value: str) -> str:
        aliases = {
            "nodes": "node",
            "node_ids": "node",
            "ports": "port",
            "port_ids": "port",
            "links": "link",
            "link_ids": "link",
        }
        if isinstance(value, str):
            return aliases.get(value.strip().lower(), value)
        return value


class ValidationReport(BaseModel):
    ok: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


class RunState(BaseModel):
    run_id: str
    session_id: str
    current_stage: Literal["ground", "logical", "physical"] | None = None
    status: Literal["running", "failed", "completed"]
    artifacts: list[ArtifactRef] = Field(default_factory=list)
