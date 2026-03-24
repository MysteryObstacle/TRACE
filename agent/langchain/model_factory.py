from __future__ import annotations

from langchain_openai import ChatOpenAI


def build_chat_model(model_name: str, temperature: float = 0.0) -> ChatOpenAI:
    return ChatOpenAI(model=model_name, temperature=temperature)
