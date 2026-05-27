from __future__ import annotations

from typing import Any, Protocol

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from trace.config.settings import TraceSettings
from trace.observability.tracing import TraceObserver


class RoleClient(Protocol):
    def invoke_structured(
        self,
        *,
        role_name: str,
        messages: list[dict[str, str]],
        schema: type[BaseModel],
    ) -> Any:
        ...

    def invoke_agent(
        self,
        *,
        role_name: str,
        messages: list[dict[str, str]],
        tools: list[Any],
        max_react_steps: int = 24,
    ) -> Any:
        ...

    def invoke(
        self,
        *,
        role_name: str,
        messages: list[dict[str, str]],
        schema: type[BaseModel] | None = None,
        tools: list[Any] | None = None,
    ) -> Any:
        ...


class LangChainRoleClient:
    def __init__(self, settings: TraceSettings, observer: TraceObserver | None = None) -> None:
        self.settings = settings
        self.observer = observer or TraceObserver(settings.langsmith)
        self._chat_openai_cache: dict[tuple[str, str, float, str], ChatOpenAI] = {}

    def _chat_openai(self, *, role_name: str) -> ChatOpenAI:
        role_settings = self.settings.roles[role_name]
        cache_key = (role_name, role_settings.model, role_settings.temperature, self.settings.openai_base_url or "")
        cached = self._chat_openai_cache.get(cache_key)
        if cached is not None:
            return cached
        model = ChatOpenAI(
            model=role_settings.model,
            temperature=role_settings.temperature,
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
        )
        self._chat_openai_cache[cache_key] = model
        return model

    def invoke_structured(
        self,
        *,
        role_name: str,
        messages: list[dict[str, str]],
        schema: type[BaseModel],
    ) -> Any:
        with self.observer.role_run(role_name, message_count=len(messages), tool_count=0):
            model = self._chat_openai(role_name=role_name)
            lc_messages = [
                SystemMessage(content="Return a valid JSON object."),
                *[_to_message(item) for item in messages],
            ]
            structured = model.with_structured_output(schema, method="json_mode")
            return structured.invoke(lc_messages)

    def invoke_agent(
        self,
        *,
        role_name: str,
        messages: list[dict[str, str]],
        tools: list[Any],
        max_react_steps: int = 24,
        max_tool_calls: int | None = None,
    ) -> Any:
        if max_tool_calls is not None:
            max_react_steps = max_tool_calls
        with self.observer.role_run(role_name, message_count=len(messages), tool_count=len(tools)):
            model = self._chat_openai(role_name=role_name)
            agent = create_react_agent(model, tools, prompt=None)
            lc_messages = [_to_message(item) for item in messages]
            return agent.invoke({"messages": lc_messages}, {"recursion_limit": max_react_steps * 2})

    def invoke(
        self,
        *,
        role_name: str,
        messages: list[dict[str, str]],
        schema: type[BaseModel] | None = None,
        tools: list[Any] | None = None,
    ) -> Any:
        if schema is not None:
            return self.invoke_structured(role_name=role_name, messages=messages, schema=schema)
        if tools:
            return self.invoke_agent(role_name=role_name, messages=messages, tools=tools)

        with self.observer.role_run(role_name, message_count=len(messages), tool_count=0):
            model = self._chat_openai(role_name=role_name)
            lc_messages = [_to_message(item) for item in messages]
            response = model.invoke(lc_messages)
            if isinstance(response, AIMessage):
                return {"content": _coerce_content(response.content)}
            return response


def _to_message(item: dict[str, str]) -> BaseMessage:
    role = item["role"]
    content = item["content"]
    if role == "system":
        return SystemMessage(content=content)
    if role == "human":
        return HumanMessage(content=content)
    return AIMessage(content=content)


def _coerce_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return str(content)
