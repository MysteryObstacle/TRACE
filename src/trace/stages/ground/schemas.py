from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from tgraph.operations.validate.constraint_files import LOGICAL_FACT_KINDS, PHYSICAL_FACT_KINDS


ALL_FACT_KINDS = LOGICAL_FACT_KINDS | PHYSICAL_FACT_KINDS
FORBIDDEN_STATEMENT_PREFIXES = ("Subnet fact:", "Interface fact:", "Graph fact:", "Image design:", "Flavor design:")

LOGICAL_CONSTRAINTS_PATH = "ground/logical_constraints.json"
PHYSICAL_CONSTRAINTS_PATH = "ground/physical_constraints.json"


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


class DraftConstraintStatement(_GroundBaseModel):
    id: str = Field(
        description="Stable constraint id, for example lc1 for logical constraints or pc1 for physical constraints.",
    )
    kind: str | None = Field(
        default=None,
        description=(
            "Fact kind aligned to checkpoint API families. Drafts may be evaluated and revised when the kind is "
            "missing, unknown, or assigned to the wrong stage."
        ),
    )
    statement: str = Field(
        description="Single executable fact as a natural-language sentence. Keep one primary semantic per statement.",
    )


class GroundDraftArtifact(_GroundBaseModel):
    node_groups: list[NodeGroup] = Field(
        default_factory=list,
        description="The complete node inventory grouped by canonical node type in node_groups.",
    )
    logical_constraints: list[DraftConstraintStatement] = Field(
        default_factory=list,
        description="Logical/topology/addressing constraints with id, kind, and statement.",
    )
    physical_constraints: list[DraftConstraintStatement] = Field(
        default_factory=list,
        description="Physical deployment constraints. Leave empty when there is no explicit physical intent.",
    )


class GroundArtifact(_GroundBaseModel):
    node_groups: list[NodeGroup] = Field(
        min_length=1,
        description="The complete node inventory grouped by canonical node type.",
    )
    constraint_files: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Relative paths to ground constraint JSON files, for example "
            '{"logical": "ground/logical_constraints.json", "physical": "ground/physical_constraints.json"}.'
        ),
    )

    @model_validator(mode="after")
    def _require_logical_constraint_file(self) -> "GroundArtifact":
        logical_path = self.constraint_files.get("logical")
        if not logical_path:
            raise ValueError("ground artifact must reference ground/logical_constraints.json")
        return self


class GroundIssue(_GroundBaseModel):
    message: str
    location: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _requires_issue_kind(self) -> "GroundIssue":
        if not self.details.get("issue_kind"):
            raise ValueError("GroundIssue.details.issue_kind is required")
        return self


class GroundEvaluationReport(_GroundBaseModel):
    passed: bool
    issues: list[GroundIssue] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def draft_constraints_to_file_payload(items: list[dict[str, Any]] | list[DraftConstraintStatement]) -> dict[str, dict[str, str]]:
    payload: dict[str, dict[str, str]] = {}
    for item in items:
        if isinstance(item, DraftConstraintStatement):
            data = item.model_dump(mode="json")
        elif isinstance(item, dict):
            data = item
        else:
            continue
        constraint_id = str(data.get("id") or "").strip()
        if not constraint_id:
            continue
        kind = str(data.get("kind") or "").strip()
        statement = str(data.get("statement") or "").strip()
        entry: dict[str, str] = {"statement": statement}
        if kind:
            entry["kind"] = kind
        payload[constraint_id] = entry
    return payload


def draft_to_constraint_file_text(items: list[dict[str, Any]] | list[DraftConstraintStatement]) -> str:
    return json.dumps(draft_constraints_to_file_payload(items), indent=2, ensure_ascii=False)


def structural_issues_from_draft(draft: dict[str, Any]) -> list[dict[str, Any]]:
    from tgraph.operations.validate.constraint_files import load_constraint_text

    issues: list[dict[str, Any]] = []
    logical_items = draft.get("logical_constraints", [])
    physical_items = draft.get("physical_constraints", [])

    logical_text = draft_to_constraint_file_text(logical_items if isinstance(logical_items, list) else [])
    physical_text = draft_to_constraint_file_text(physical_items if isinstance(physical_items, list) else [])

    for scope, text in (("logical", logical_text), ("physical", physical_text)):
        result = load_constraint_text(text, source=f"ground/{scope}_constraints.json", scope=scope)
        for issue in result.issues:
            issues.append(_validation_issue_to_ground_issue(issue.model_dump(mode="json")))
    return issues


def _validation_issue_to_ground_issue(issue: dict[str, Any]) -> dict[str, Any]:
    details = dict(issue.get("details") or {})
    details.setdefault("issue_kind", details.get("issue_kind") or "ground.structural.invalid")
    return {
        "message": str(issue.get("message") or "constraint validation failed"),
        "location": issue.get("location"),
        "details": details,
    }
