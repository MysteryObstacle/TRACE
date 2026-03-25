from __future__ import annotations

import json
import orjson
import re
from typing import Any

from agent.langchain.tracing import TraceRecorder
from agent.langchain.message_codec import build_messages
from agent.types import AgentRequest, AgentResult
from langchain_core.messages import AIMessage


class FakeAgentFacade:
    def __init__(
        self,
        fixtures: dict[str, AgentResult | list[AgentResult]],
        tracer: TraceRecorder | None = None,
        reporter: Any | None = None,
    ) -> None:
        self.fixtures = fixtures
        self.requests: list[AgentRequest] = []
        self.tracer = tracer or TraceRecorder(enabled=False)
        self.reporter = reporter

    def invoke(self, request: AgentRequest) -> AgentResult:
        with self._agent_trace(request):
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

    def _agent_trace(self, request: AgentRequest):
        return self.tracer.agent_run(
            stage_id=request.stage_id,
            prompt=request.prompt,
            runtime_mode=request.inputs.get('runtime.mode'),
            input_keys=sorted(request.inputs.keys()),
        )


class LangChainAgentFacade:
    def __init__(self, engine, tracer: TraceRecorder | None = None, reporter: Any | None = None) -> None:
        self.engine = engine
        self.tracer = tracer or TraceRecorder(enabled=False)
        self.reporter = reporter

    def invoke(self, request: AgentRequest) -> AgentResult:
        with self.tracer.agent_run(
            stage_id=request.stage_id,
            prompt=request.prompt,
            runtime_mode=request.inputs.get('runtime.mode'),
            input_keys=sorted(request.inputs.keys()),
        ):
            messages = build_messages(request)
            response = self._invoke_engine(messages, request)
            output = self._extract_output(response)
            return AgentResult(stage_id=request.stage_id, output=output)

    def _invoke_engine(self, messages: list[Any], request: AgentRequest) -> Any:
        if not self._streaming_enabled():
            return self.engine.invoke(messages)

        self._report('llm_stream_started', request.stage_id, request.inputs.get('runtime.mode'))
        try:
            return self._stream_response(messages, request.stage_id)
        finally:
            self._report('llm_stream_completed', request.stage_id)

    def _stream_response(self, messages: list[Any], stage_id: str) -> Any:
        chunks: list[Any] = []
        texts: list[str] = []
        for chunk in self.engine.stream(messages):
            chunks.append(chunk)
            text = self._coerce_content_text(getattr(chunk, 'content', None))
            if text:
                texts.append(text)
                self._report('llm_stream_chunk', stage_id, text)
        if not chunks:
            return self.engine.invoke(messages)
        if len(chunks) == 1:
            return chunks[0]
        combined = chunks[0]
        try:
            for chunk in chunks[1:]:
                combined = combined + chunk
            return combined
        except Exception:
            return AIMessage(content=''.join(texts))

    def _streaming_enabled(self) -> bool:
        if self.reporter is None:
            return False
        if getattr(self.reporter, 'stream_enabled', None) is False:
            return False
        return (
            hasattr(self.reporter, 'llm_stream_started')
            and hasattr(self.reporter, 'llm_stream_chunk')
            and hasattr(self.reporter, 'llm_stream_completed')
            and hasattr(self.engine, 'stream')
        )

    def _report(self, method_name: str, *args: Any) -> None:
        if self.reporter is None:
            return
        method = getattr(self.reporter, method_name, None)
        if callable(method):
            method(*args)

    def _extract_output(self, response):
        if isinstance(response, dict) and 'output' in response:
            return response['output']
        content = getattr(response, 'content', None)
        text = self._coerce_content_text(content)
        if text is not None:
            return self._parse_json_payload(text)
        raise TypeError('Unsupported LangChain engine response shape.')

    @staticmethod
    def _coerce_content_text(content: Any) -> str | None:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and isinstance(item.get('text'), str):
                    parts.append(item['text'])
            return ''.join(parts) if parts else None
        return None

    @staticmethod
    def _parse_json_payload(text: str) -> dict[str, Any]:
        stripped = text.strip()
        try:
            return orjson.loads(stripped)
        except orjson.JSONDecodeError:
            pass

        fenced = re.search(r"```(?:json)?\s*(.*?)```", stripped, flags=re.IGNORECASE | re.DOTALL)
        if fenced is not None:
            candidate = fenced.group(1).strip()
            try:
                return orjson.loads(candidate)
            except orjson.JSONDecodeError:
                stripped = candidate

        decoder = json.JSONDecoder()
        for index, char in enumerate(stripped):
            if char not in '{[':
                continue
            try:
                payload, _ = decoder.raw_decode(stripped[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload

        raise TypeError('Model response did not contain a parseable JSON object.')
