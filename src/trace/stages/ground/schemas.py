from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _GroundBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NodeGroup(_GroundBaseModel):
    type: Literal["switch", "router", "computer"] = Field(
        description="Canonical TRACE node type. Use only switch, router, or computer.",
    )
    members: list[str] = Field(
        min_length=1,
        description=(
            "Concrete canonical node identifiers in this type bucket, for example SWITCH1, ROUTER1, PLC1, "
            "or compact ranges such as PLC[1..6]. Do not use role labels as members."
        ),
    )


class ConstraintStatement(_GroundBaseModel):
    id: str = Field(
        description="Stable constraint id, for example lc1 for logical constraints or pc1 for physical constraints.",
    )
    statement: str = Field(
        description="Single 可执行 fact as a natural-language sentence. Keep one primary semantic per statement.",
    )


class GroundArtifact(_GroundBaseModel):
    node_groups: list[NodeGroup] = Field(
        min_length=1,
        description="完整节点清单，按 canonical node type 分组后写入 node_groups。Must not be empty for accepted artifacts.",
    )
    logical_constraints: list[ConstraintStatement] = Field(
        default_factory=list,
        description=(
            "logical/topology/addressing/segmentation constraints. Each item must be an object with only id and "
            "statement, not a bare string."
        ),
    )
    physical_constraints: list[ConstraintStatement] = Field(
        default_factory=list,
        description=(
            "deployment/image/runtime/resource constraints aligned to node metadata. Use only when the intent "
            "explicitly states deployment, image, runtime, appliance, or resource requirements."
        ),
    )


class GroundDraftArtifact(_GroundBaseModel):
    node_groups: list[NodeGroup] = Field(
        default_factory=list,
        description="完整节点清单，按 canonical node type 分组后写入 node_groups。Drafts should preserve explicit inventory.",
    )
    logical_constraints: list[ConstraintStatement] = Field(
        default_factory=list,
        description=(
            "logical/topology/addressing/segmentation constraints. Each item must be an object with only id and "
            "statement, not a bare string."
        ),
    )
    physical_constraints: list[ConstraintStatement] = Field(
        default_factory=list,
        description=(
            "deployment/image/runtime/resource constraints aligned to node metadata. Leave empty only when there is "
            "no explicit physical deployment intent."
        ),
    )


class GroundIssue(_GroundBaseModel):
    code: str
    message: str
    location: str | None = None


class GroundOptimizerBrief(_GroundBaseModel):
    node_groups: list[NodeGroup] = Field(default_factory=list)
    logical_constraints: list[ConstraintStatement] = Field(default_factory=list)
    physical_constraints: list[ConstraintStatement] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class GroundEvaluationReport(_GroundBaseModel):
    passed: bool
    issues: list[GroundIssue] = Field(default_factory=list)
    optimizer_brief: GroundOptimizerBrief = Field(default_factory=GroundOptimizerBrief)
