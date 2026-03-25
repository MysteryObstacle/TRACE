from __future__ import annotations

from typing import Any


class LangChainEngine:
    def __init__(self, model: Any) -> None:
        self.model = model

    def invoke(self, messages: list[Any]) -> Any:
        return self.model.invoke(messages)

    def stream(self, messages: list[Any]):
        stream = getattr(self.model, 'stream', None)
        if callable(stream):
            yield from stream(messages)
            return
        yield self.model.invoke(messages)
