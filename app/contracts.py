from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ArtifactSelector(BaseModel):
    stage: Literal["ground", "logical", "physical"]
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
    scope: Literal["node_ids", "topology"]
    targets: list[str] = Field(default_factory=list)
    json_paths: list[str] = Field(default_factory=list)


class ValidationReport(BaseModel):
    ok: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


class RunState(BaseModel):
    run_id: str
    session_id: str
    current_stage: Literal["ground", "logical", "physical"] | None = None
    status: Literal["running", "failed", "completed"]
    artifacts: list[ArtifactRef] = Field(default_factory=list)
