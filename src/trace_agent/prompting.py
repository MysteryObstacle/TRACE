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
    tool_usage_guide = dedent(
        """
        工具使用策略（请按需调用，避免跳步）:
        1) Plan Context Query: 先读取已有步骤/回合结论，保证连贯性。
        2) Domain Knowledge: 获取行业/普渡模型等分区经验，用于宏观架构。
        3) Topo Spec / SceneGraph Code Spec: 生成前先查规范，避免字段/方法错误。
        4) Topo Source JSON / Topo Target JSON: 仅在需要读取/初始化当前或目标拓扑时使用。
        5) Topo Diff Planner: 只有在新旧拓扑已明确时再对比生成diff。
        6) SceneGraph SDK: 仅在输出代码或校验接口时调用。
        7) Image Catalog: 仅在需要镜像选择/部署建议时调用。

        步骤期望:
        - Step 1 先用 Domain Knowledge + Plan Context Query 给出分层/区域文字描述，不直接生成JSON。
        - Step 2 基于 Step 1 结论与规范汇总候选节点类型与职责（文字为主）。
        - Step 3 划分区域/组，引用前序结论，必要时再查询规范。
        - Step 4 补充节点属性/镜像，先查规范或镜像工具再写JSON。
        - Step 5/6 生成JSON/SceneGraph代码前务必先确认规范，必要时再做diff。
        - Step 7 验证时可用 Diff/SDK 工具，返回校验结果。
        """
    )

    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                SYSTEM_PRIMER
                + "\n"
                + dedent(
                    """
                    输出严格遵循三段式：
                    Think: 你的推理过程（包含使用哪些工具、为何按此顺序）
                    Action: 调用的工具或操作，如果无需调用工具请写"N/A"
                    Observe: 根据Action得到的结果或基于思考的结论
                    当你认为当前计划步骤的目标已经达成，请在Observe开头添加"[FINISHED]"并给出简要结论；否则继续推进该步骤。
                    请优先检索历史上下文与领域知识，不要直接生成最终JSON/代码，除非该步骤明确要求。
                    """
                )
                + "\n"
                + tool_usage_guide,
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
