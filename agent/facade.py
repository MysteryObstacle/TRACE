from __future__ import annotations

import orjson

from agent.langchain.message_codec import build_messages
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


class LangChainAgentFacade:
    def __init__(self, engine) -> None:
        self.engine = engine

    def invoke(self, request: AgentRequest) -> AgentResult:
        messages = build_messages(request)
        response = self.engine.invoke(messages)
        output = self._extract_output(response)
        return AgentResult(stage_id=request.stage_id, output=output)

    def _extract_output(self, response):
        if isinstance(response, dict) and 'output' in response:
            return response['output']
        if hasattr(response, 'content') and isinstance(response.content, str):
            return orjson.loads(response.content)
        raise TypeError('Unsupported LangChain engine response shape.')
