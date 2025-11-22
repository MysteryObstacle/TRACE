from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel

from .memory import ConversationState, PlanContext, PlanStep, StepResult
from .prompting import GOAL_EXTRACTION_PROMPT, SCENE_TASK_CLASSIFIER, build_react_prompt
from .tools import Toolset


@dataclass
class AgentConfig:
    auto_execute: bool = True
    default_tools: Optional[Toolset] = None


class TraceAgent:
    """TRACE agent orchestrating the PLAN + ReAct loop."""

    def __init__(self, llm: BaseChatModel, config: Optional[AgentConfig] = None) -> None:
        self.llm = llm
        self.config = config or AgentConfig()
        self.state = ConversationState()
        self.tools = self.config.default_tools or Toolset()

    def initialize_state(self, topo_state: Optional[dict] = None) -> None:
        if topo_state:
            self.state.set_topology(topo_state)

    def derive_goal(self, user_intent: str) -> str:
        topo_summary = self.state.topo_json.get("summary", "(空拓扑)") if self.state.topo_json else "(空拓扑)"
        prompt = GOAL_EXTRACTION_PROMPT.invoke(
            {"user_intent": user_intent, "topo_summary": topo_summary}
        )
        response = self.llm.invoke(prompt)
        goal = response.content if hasattr(response, "content") else str(response)
        self.state.set_goal(goal.strip())
        return goal.strip()

    def is_scene_construction_goal(self) -> bool:
        if not self.state.overall_goal:
            return False
        prompt = SCENE_TASK_CLASSIFIER.invoke({"overall_goal": self.state.overall_goal})
        response = self.llm.invoke(prompt)
        answer = (response.content if hasattr(response, "content") else str(response)).lower()
        return "yes" in answer

    def generate_plan(self) -> list[PlanStep]:
        return [
            PlanStep.UNDERSTAND_INTENT,
            PlanStep.SELECT_NODE_TYPES,
            PlanStep.DIVIDE_ZONES,
            PlanStep.ASSIGN_NODE_ATTRIBUTES,
            PlanStep.GENERATE_JSON,
            PlanStep.GENERATE_SCENEGRAPH,
            PlanStep.VERIFY_CODE,
        ]

    def run_plan(self, user_intent: str, topo_state: Optional[dict] = None) -> PlanContext:
        self.initialize_state(topo_state)
        self.derive_goal(user_intent)
        if not self.is_scene_construction_goal():
            summary = (
                "Think: 用户目标不需要SceneGraph代码\n"
                "Action: N/A\n"
                "Observe: 任务结束"
            )
            result = self._parse_react_blocks(summary)
            self.state.record_step(PlanStep.UNDERSTAND_INTENT, result)
            return self.state.plan_context

        for step in self.generate_plan():
            self.state.set_current_step(step)
            step_result = self._run_react_step(step, user_intent)
            self.state.record_step(step, step_result)
        return self.state.plan_context

    def _run_react_step(self, step: PlanStep, user_intent: str) -> StepResult:
        prompt = build_react_prompt(step, self.tools.tool_names())
        prompt_to_send = prompt.invoke(
            {
                "context": self._context_snippet(),
                "user_intent": user_intent,
                "topo_summary": self.state.topo_json.get("summary", "(空拓扑)"),
            }
        )
        response = self.llm.invoke(prompt_to_send)
        content = response.content if hasattr(response, "content") else str(response)
        return self._parse_react_blocks(content)

    def _context_snippet(self) -> str:
        parts: list[str] = []
        for step, results in self.state.plan_context.steps.items():
            for idx, result in enumerate(results, start=1):
                parts.append(f"{step.label} #{idx}: {result.observe}")
        return "\n".join(parts) if parts else "(无历史上下文)"

    def _parse_react_blocks(self, content: str) -> StepResult:
        think, action, observe = "", "", ""
        for line in content.splitlines():
            if line.startswith("Think:"):
                think = line.partition(":")[2].strip()
            elif line.startswith("Action:"):
                action = line.partition(":")[2].strip()
            elif line.startswith("Observe:"):
                observe = line.partition(":")[2].strip()
        if not think:
            think = content.strip()
        return StepResult(think=think, action=action or "N/A", observe=observe or content.strip(), output=None)

    def plan_outline(self) -> str:
        steps = [step.label for step in self.generate_plan()]
        return "PLAN:\n" + "\n".join(steps)

    def available_tools(self) -> str:
        return self.tools.describe()

    def provide_persistent_prompts(self, prompts: dict[str, str]) -> None:
        self.state.persistent_prompts.update(prompts)
