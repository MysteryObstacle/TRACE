from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.types import Command

from trace.stages.stage_results import compile_repair_stage_graph


class _TinyState(TypedDict, total=False):
    trace: Annotated[list[str], operator.add]


def test_repair_stage_graph_lets_repair_command_choose_next_node():
    def _step(name: str):
        return lambda _state: {"trace": [name]}

    def _validator(state: _TinyState):
        if "repair" in state.get("trace", []):
            return Command(goto="finalize", update={"trace": ["validator-after-repair"]})
        return Command(goto="repair", update={"trace": ["validator"]})

    def _repair(_state: _TinyState):
        return Command(goto="escalate", update={"trace": ["repair"]})

    graph = compile_repair_stage_graph(
        _TinyState,
        nodes={
            "prepare": _step("prepare"),
            "author": _step("author"),
            "builder": _step("builder"),
            "validator": _validator,
            "repair": _repair,
            "finalize": _step("finalize"),
            "escalate": _step("escalate"),
        },
    )

    result = graph.invoke({"trace": []})

    assert result["trace"] == ["prepare", "author", "builder", "validator", "repair", "escalate"]
