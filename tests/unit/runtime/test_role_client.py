from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from trace.config.settings import load_settings
from trace.runtime.role_client import LangChainRoleClient


class DemoSchema(BaseModel):
    value: str


def test_role_client_invoke_structured_uses_model_name_and_openai_credentials(monkeypatch):
    captured = {}

    class FakeStructuredModel:
        def invoke(self, messages):
            captured["structured_messages"] = messages
            return DemoSchema(value="ok")

    class FakeModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def with_structured_output(self, schema, **kwargs):
            captured["schema"] = schema
            captured["structured_kwargs"] = kwargs
            return FakeStructuredModel()

    monkeypatch.setattr("trace.runtime.role_client.ChatOpenAI", FakeModel)
    settings = load_settings(
        openai_api_key="test-openai-key",
        openai_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="qwen-plus-2025-07-28",
    )

    client = LangChainRoleClient(settings)
    result = client.invoke_structured(
        role_name="ground_author",
        messages=[{"role": "system", "content": "sys"}, {"role": "human", "content": "hi"}],
        schema=DemoSchema,
    )

    assert result == DemoSchema(value="ok")
    assert captured["model"] == "qwen-plus-2025-07-28"
    assert captured["api_key"] == "test-openai-key"
    assert captured["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert captured["schema"] is DemoSchema
    assert captured["structured_kwargs"] == {"method": "json_mode"}
    assert captured["structured_messages"] == [
        SystemMessage(content="Return a valid JSON object."),
        SystemMessage(content="sys"),
        HumanMessage(content="hi"),
    ]


def test_role_client_invoke_agent_uses_react_agent_with_tools(monkeypatch):
    captured = {}

    class FakeAgent:
        def invoke(self, payload, config):
            captured["payload"] = payload
            captured["config"] = config
            return {"messages": [{"role": "assistant", "content": "done"}]}

    class FakeModel:
        def __init__(self, **kwargs):
            captured["init"] = kwargs

    def fake_create_react_agent(model, tools, prompt):
        captured["agent_model"] = model
        captured["tools"] = tools
        captured["prompt"] = prompt
        return FakeAgent()

    monkeypatch.setattr("trace.runtime.role_client.ChatOpenAI", FakeModel)
    monkeypatch.setattr("trace.runtime.role_client.create_react_agent", fake_create_react_agent)
    settings = load_settings(
        openai_api_key="test-openai-key",
        openai_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="qwen-plus-2025-07-28",
    )

    client = LangChainRoleClient(settings)
    result = client.invoke_agent(
        role_name="logical_repair",
        messages=[{"role": "system", "content": "repair sys"}, {"role": "human", "content": "fix it"}],
        tools=["tool-a"],
        max_tool_calls=9,
    )

    assert result == {"messages": [{"role": "assistant", "content": "done"}]}
    assert captured["tools"] == ["tool-a"]
    assert captured["payload"] == {
        "messages": [
            SystemMessage(content="repair sys"),
            HumanMessage(content="fix it"),
        ]
    }
    assert captured["config"] == {"recursion_limit": 9}
    assert captured["prompt"] is None


def test_role_client_invoke_structured_prepends_json_contract_message(monkeypatch):
    captured = {}

    class FakeStructuredModel:
        def invoke(self, messages):
            captured["structured_messages"] = messages
            return DemoSchema(value="ok")

    class FakeModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def with_structured_output(self, schema, **kwargs):
            captured["schema"] = schema
            captured["structured_kwargs"] = kwargs
            return FakeStructuredModel()

    monkeypatch.setattr("trace.runtime.role_client.ChatOpenAI", FakeModel)
    settings = load_settings(
        openai_api_key="test-openai-key",
        openai_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="qwen-plus-2025-07-28",
    )

    client = LangChainRoleClient(settings)
    result = client.invoke_structured(
        role_name="ground_author",
        messages=[
            {"role": "system", "content": "return json object"},
            {"role": "human", "content": "hi"},
        ],
        schema=DemoSchema,
    )

    assert result == DemoSchema(value="ok")
    assert captured["structured_kwargs"] == {"method": "json_mode"}
    assert captured["structured_messages"] == [
        SystemMessage(content="Return a valid JSON object."),
        SystemMessage(content="return json object"),
        HumanMessage(content="hi"),
    ]
