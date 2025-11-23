from __future__ import annotations

from langchain_community.chat_models import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel


DEFAULT_QWEN_MODEL = "Qwen3-1.5B"


def build_qwen_vllm_chat_model(
    base_url: str,
    api_key: str = "EMPTY",
    model: str = DEFAULT_QWEN_MODEL,
    **kwargs: object,
) -> BaseChatModel:
    """Build a ChatOpenAI-compatible client that targets a vLLM + Qwen3 endpoint.

    The implementation relies on the OpenAI-compatible HTTP route exposed by vLLM
    and keeps the constructor signature intentionally simple so it can be wired
    into LangChain's graph or agent tooling without additional adapters.
    """

    normalized_base = base_url.rstrip("/")
    if normalized_base.endswith("/chat/completions"):
        normalized_base = normalized_base[: -len("/chat/completions")]

    return ChatOpenAI(
        openai_api_base=normalized_base,
        openai_api_key=api_key,
        model=model,
        streaming=kwargs.get("streaming", False),
        temperature=kwargs.get("temperature", 0.3),
        max_tokens=kwargs.get("max_tokens", 2048),
    )
