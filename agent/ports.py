from __future__ import annotations

from typing import Protocol

from agent.types import AgentRequest, AgentResult


class ReasonerPort(Protocol):
    def invoke(self, request: AgentRequest) -> AgentResult:
        ...
