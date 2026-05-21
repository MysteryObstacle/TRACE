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
        max_tool_calls: int = 12,
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

    def invoke_structured(
        self,
        *,
        role_name: str,
        messages: list[dict[str, str]],
        schema: type[BaseModel],
    ) -> Any:
        role_settings = self.settings.roles[role_name]
        with self.observer.role_run(role_name, message_count=len(messages), tool_count=0):
            model = ChatOpenAI(
                model=role_settings.model,
                temperature=role_settings.temperature,
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
            )
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
        max_tool_calls: int = 12,
    ) -> Any:
        role_settings = self.settings.roles[role_name]
        with self.observer.role_run(role_name, message_count=len(messages), tool_count=len(tools)):
            model = ChatOpenAI(
                model=role_settings.model,
                temperature=role_settings.temperature,
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
            )
            agent = create_react_agent(model, tools, prompt=None)
            lc_messages = [_to_message(item) for item in messages]
            return agent.invoke({"messages": lc_messages}, {"recursion_limit": max_tool_calls})

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

        role_settings = self.settings.roles[role_name]
        with self.observer.role_run(role_name, message_count=len(messages), tool_count=0):
            model = ChatOpenAI(
                model=role_settings.model,
                temperature=role_settings.temperature,
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
            )
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
