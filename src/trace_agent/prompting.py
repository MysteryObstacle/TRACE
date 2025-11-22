from __future__ import annotations

from textwrap import dedent
from typing import Iterable

from langchain_core.prompts import ChatPromptTemplate

from .memory import PlanStep


SYSTEM_PRIMER = dedent(
    """
    你是TRACE，一名Topology-Reasoning Agent，负责在受控环境下按照SceneGraph规范生成网络拓扑。
    遵循TypeScript脚本规范、Topo规范和SceneGraph SDK接口，严格执行ReAct范式，保持中文输出。
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


def build_react_prompt(step: PlanStep, tools: Iterable[str]) -> ChatPromptTemplate:
    """Construct a ReAct-style prompt for the given plan step."""

    tools_text = "\n".join(f"- {tool}" for tool in tools) or "(无可用工具，直接思考)"
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                SYSTEM_PRIMER
                + "\n"
                + dedent(
                    """
                    输出严格遵循三段式：
                    Think: 你的推理过程
                    Action: 调用的工具或操作，如果无需调用工具请写"N/A"
                    Observe: 根据Action得到的结果或基于思考的结论
                    当你认为当前计划步骤的目标已经达成，请在Observe开头添加"[FINISHED]"并给出简要结论；否则继续推进该步骤。
                    """
                ),
            ),
            (
                "human",
                dedent(
                    """
                    当前计划步骤: {step_label}
                    相关上下文: {context}
                    可用工具:
                    {tools}
                    用户意图: {user_intent}
                    拓扑摘要: {topo_summary}
                    如需生成结构化JSON或SceneGraph代码，请包含在Observe中。
                    """
                ),
            ),
        ]
    ).partial(step_label=step.label, tools=tools_text)
