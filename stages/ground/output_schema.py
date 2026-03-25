import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ConstraintItem(BaseModel):
    id: str
    scope: Literal["node_ids", "topology"]
    text: str


class GroundOutput(BaseModel):
    node_patterns: list[str] = Field(default_factory=list)
    logical_constraints: list[ConstraintItem] = Field(default_factory=list)
    physical_constraints: list[ConstraintItem] = Field(default_factory=list)

    @field_validator('logical_constraints', mode='before')
    @classmethod
    def _normalize_logical_constraints(cls, value):
        return _normalize_constraints(value, prefix='lc')

    @field_validator('physical_constraints', mode='before')
    @classmethod
    def _normalize_physical_constraints(cls, value):
        return _normalize_constraints(value, prefix='pc')


def _normalize_constraints(value, *, prefix: str) -> list[dict]:
    if value is None:
        return []

    normalized: list[dict] = []
    for index, item in enumerate(value, start=1):
        if isinstance(item, str):
            normalized.append(
                {
                    'id': f'{prefix}{index}',
                    'scope': _infer_scope(item),
                    'text': item,
                }
            )
            continue
        normalized.append(item)
    return normalized


def _infer_scope(text: str) -> str:
    if '[' in text and '..' in text and ']' in text:
        return 'node_ids'
    return 'topology'


def sanitize_ground_output(output: GroundOutput) -> GroundOutput:
    logical = list(output.logical_constraints)
    physical: list[ConstraintItem] = []

    for constraint in output.physical_constraints:
        text_lower = constraint.text.lower()
        if _is_switch_capability_constraint(text_lower):
            continue
        if _is_topological_physical_constraint(text_lower):
            logical.append(
                ConstraintItem(
                    id=f'lc_from_{constraint.id}',
                    scope='topology',
                    text=constraint.text,
                )
            )
            continue
        physical.append(constraint)

    return GroundOutput(
        node_patterns=output.node_patterns,
        logical_constraints=[item.model_dump(mode='json') for item in logical],
        physical_constraints=[item.model_dump(mode='json') for item in physical],
    )


def _is_switch_capability_constraint(text_lower: str) -> bool:
    return 'switch' in text_lower and ('vlan' in text_lower or 'managed switch' in text_lower)


def _is_topological_physical_constraint(text_lower: str) -> bool:
    return any(token in text_lower for token in ['interconnect', 'connect ', 'connectivity', ' through ', ' via '])
