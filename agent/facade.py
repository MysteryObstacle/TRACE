from __future__ import annotations

from agent.types import AgentRequest, AgentResult


class FakeAgentFacade:
    def __init__(self, fixtures: dict[str, AgentResult]) -> None:
        self.fixtures = fixtures

    def invoke(self, request: AgentRequest) -> AgentResult:
        try:
            return self.fixtures[request.stage_id]
        except KeyError as exc:
            raise KeyError(f'No fixture configured for stage: {request.stage_id}') from exc
