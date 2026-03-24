from __future__ import annotations

import orjson
from langchain_core.messages import HumanMessage, SystemMessage

from agent.types import AgentRequest


def build_messages(request: AgentRequest):
    payload = orjson.dumps(request.inputs, option=orjson.OPT_INDENT_2).decode()
    return [
        SystemMessage(content=request.prompt),
        HumanMessage(content=payload),
    ]
