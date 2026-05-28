from unittest.mock import patch

from trace.config.settings import load_settings
from trace.runtime.role_client import LangChainRoleClient


def test_chat_openai_cached_for_same_role_signature():
    settings = load_settings(
        openai_api_key="sk-test",
        openai_base_url="https://example/v1",
        role_logical_repair_model="gpt-4o-mini",
    )
    client = LangChainRoleClient(settings)
    with patch("trace.runtime.role_client.ChatOpenAI") as ChatOpenAIMock:
        ChatOpenAIMock.return_value = object()
        client._chat_openai(role_name="logical_repair")
        client._chat_openai(role_name="logical_repair")
        assert ChatOpenAIMock.call_count == 1


def test_chat_openai_distinct_role_creates_separate_instance():
    settings = load_settings(
        openai_api_key="sk-test",
        openai_base_url="https://example/v1",
        role_logical_repair_model="gpt-4o-mini",
        role_logical_author_model="gpt-4o",
        role_logical_author_temperature=0.2,
    )
    client = LangChainRoleClient(settings)
    with patch("trace.runtime.role_client.ChatOpenAI") as ChatOpenAIMock:
        ChatOpenAIMock.return_value = object()
        client._chat_openai(role_name="logical_repair")
        client._chat_openai(role_name="logical_author")
        assert ChatOpenAIMock.call_count == 2
