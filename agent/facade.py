from __future__ import annotations

from agent.types import AgentRequest, AgentResult


class FakeAgentFacade:
    def __init__(self, fixtures: dict[str, AgentResult | list[AgentResult]]) -> None:
        self.fixtures = fixtures
        self.requests: list[AgentRequest] = []

    def invoke(self, request: AgentRequest) -> AgentResult:
        self.requests.append(request)
        try:
            fixture = self.fixtures[request.stage_id]
        except KeyError as exc:
            raise KeyError(f'No fixture configured for stage: {request.stage_id}') from exc

        if isinstance(fixture, list):
            if not fixture:
                raise KeyError(f'No remaining fixtures configured for stage: {request.stage_id}')
            return fixture.pop(0)
        return fixture
