from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tgraph.operations.validate.issues import ValidationIssue, validation_issue

ConstraintScope = Literal["logical", "physical"]

LOGICAL_FACT_KINDS = {
    "logical.addressing.subnet",
    "logical.addressing.interface",
    "logical.topology.direct",
    "logical.topology.chain",
    "logical.topology.ring",
    "logical.topology.star",
    "logical.topology.mesh",
    "logical.custom",
}

PHYSICAL_FACT_KINDS = {
    "physical.image.capability",
    "physical.image.exact",
    "physical.flavor.minimum",
    "physical.flavor.exact",
    "physical.custom",
}


class ConstraintFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    statement: str


class ConstraintFileResult(BaseModel):
    ok: bool
    constraints: dict[str, ConstraintFact] = Field(default_factory=dict)
    issues: list[ValidationIssue] = Field(default_factory=list)

    @classmethod
    def from_issues(
        cls,
        constraints: dict[str, ConstraintFact],
        issues: list[ValidationIssue],
    ) -> "ConstraintFileResult":
        return cls(ok=not any(issue.severity == "error" for issue in issues), constraints=constraints, issues=issues)


def load_constraint_file(path: str | Path, *, scope: ConstraintScope) -> ConstraintFileResult:
    source = str(path).replace("\\", "/")
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        return ConstraintFileResult.from_issues(
            {},
            [
                validation_issue(
                    "constraint.file.read_error",
                    f"failed to read constraint file: {exc}",
                    location=source,
                    details={"source": source},
                )
            ],
        )
    return load_constraint_text(text, source=source, scope=scope)


def load_constraint_text(text: str, *, source: str, scope: ConstraintScope) -> ConstraintFileResult:
    duplicate_keys: list[str] = []
    try:
        raw = json.loads(text, object_pairs_hook=_object_pairs_hook(duplicate_keys))
    except json.JSONDecodeError as exc:
        return ConstraintFileResult.from_issues(
            {},
            [
                validation_issue(
                    "constraint.file.invalid_json",
                    f"constraint file is not valid JSON: {exc.msg}",
                    location=source,
                    details={"source": source, "line": exc.lineno, "column": exc.colno},
                )
            ],
        )

    if not isinstance(raw, dict):
        return ConstraintFileResult.from_issues(
            {},
            [
                validation_issue(
                    "constraint.file.invalid_shape",
                    "constraint file must be a JSON object keyed by constraint id",
                    location=source,
                    details={"source": source},
                )
            ],
        )

    constraints: dict[str, ConstraintFact] = {}
    issues: list[ValidationIssue] = []

    for duplicate_key in sorted(set(duplicate_keys)):
        issues.append(
            validation_issue(
                "constraint.file.duplicate_key",
                f"constraint id appears more than once: {duplicate_key}",
                location=f"{source}.{duplicate_key}",
                details={"source": source, "duplicate_key": duplicate_key},
            )
        )

    allowed_kinds = LOGICAL_FACT_KINDS if scope == "logical" else PHYSICAL_FACT_KINDS
    for constraint_id, payload in raw.items():
        if not isinstance(payload, dict):
            issues.append(
                validation_issue(
                    "constraint.file.invalid_shape",
                    f"constraint {constraint_id} must be an object",
                    location=f"{source}.{constraint_id}",
                    details={"source": source, "constraint_id": str(constraint_id)},
                )
            )
            continue

        try:
            fact = ConstraintFact.model_validate(payload)
        except ValidationError as exc:
            issues.append(
                validation_issue(
                    "constraint.file.invalid_shape",
                    f"constraint {constraint_id} has invalid shape",
                    location=f"{source}.{constraint_id}",
                    details={"source": source, "constraint_id": str(constraint_id), "errors": exc.errors()},
                )
            )
            continue

        constraints[str(constraint_id)] = fact
        if fact.kind not in allowed_kinds:
            issues.append(
                validation_issue(
                    "constraint.kind.unknown",
                    f"constraint {constraint_id} uses unknown {scope} fact kind: {fact.kind}",
                    location=f"{source}.{constraint_id}.kind",
                    details={
                        "source": source,
                        "constraint_id": str(constraint_id),
                        "fact_kind": fact.kind,
                        "allowed_kinds": sorted(allowed_kinds),
                    },
                )
            )

    return ConstraintFileResult.from_issues(constraints, issues)


def _object_pairs_hook(duplicate_keys: list[str]):
    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                duplicate_keys.append(key)
            result[key] = value
        return result

    return hook
