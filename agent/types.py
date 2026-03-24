from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    stage_id: str
    prompt: str
    inputs: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    stage_id: str
    output: dict[str, Any] = Field(default_factory=dict)
