from __future__ import annotations

import orjson
from pathlib import Path
from langchain_core.messages import HumanMessage, SystemMessage

from agent.types import AgentRequest


def build_messages(request: AgentRequest):
    return [
        SystemMessage(content=_load_prompt_content(request.prompt)),
        HumanMessage(content=_build_human_content(request.inputs)),
    ]


def _load_prompt_content(prompt: str) -> str:
    path = Path(prompt)
    if path.exists() and path.is_file():
        return path.read_text(encoding='utf-8')
    return prompt


def _build_human_content(inputs: dict[str, object]) -> str:
    intent = inputs.get('runtime.intent')
    remaining_inputs = {key: value for key, value in inputs.items() if key != 'runtime.intent'}
    sections: list[str] = [
        'Use the real user intent below as the task to solve. Treat any examples in the system prompt as schema examples only.'
    ]

    if isinstance(intent, str) and intent.strip():
        sections.append(f'REAL USER INTENT:\n{intent.strip()}')

    header = 'OTHER RUNTIME INPUTS (JSON):' if remaining_inputs and intent else 'RUNTIME INPUTS (JSON):'
    if remaining_inputs:
        payload = orjson.dumps(remaining_inputs, option=orjson.OPT_INDENT_2).decode()
        sections.append(f'{header}\n{payload}')
    elif intent is None:
        sections.append('RUNTIME INPUTS (JSON):\n{}')

    return '\n\n'.join(sections)
