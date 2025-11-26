from __future__ import annotations

from textwrap import dedent
from typing import Iterable

from langchain_core.prompts import ChatPromptTemplate

from .memory import PlanStep


SYSTEM_PRIMER = dedent(
    """
    你是TRACE，一名Topology-Reasoning Agent，负责在受控环境下按照SceneGraph规范生成网络拓扑。
    遵循TypeScript脚本规范、Topo规范和SceneGraph SDK接口，保持中文输出。
    """
)

GOAL_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PRIMER),
        (
            "human",
            dedent(
                """
                用户意图: {user_intent}
                当前拓扑摘要: {topo_summary}
                请用一两句话概览总体目标，仅输出目标本身。
                """
            ),
        ),
    ]
)

SCENE_TASK_CLASSIFIER = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PRIMER),
        (
            "human",
            dedent(
                """
                判断总体目标是否需要生成SceneGraph代码，回答"yes"或"no"。
                目标: {overall_goal}
                """
            ),
        ),
    ]
)


def build_step_prompt(
    step: PlanStep,
    tools: Iterable[str],
    *,
    context: str,
    user_intent: str,
    topo_summary: str,
) -> str:
    """Construct a concise human message for the given plan step."""

    tools_text = "\n".join(f"- {tool}" for tool in tools) or "(无可用工具，直接思考)"
    return dedent(
        """
        当前计划步骤: {step_label}
        相关上下文: {context}
        可用工具:
        {tools}
        用户意图: {user_intent}
        拓扑摘要: {topo_summary}
        请按需调用工具完成本步骤目标，如需生成结构化JSON或SceneGraph代码请直接给出。
        """
    ).format(
        step_label=step.label,
        tools=tools_text,
        context=context,
        user_intent=user_intent,
        topo_summary=topo_summary,
    )
