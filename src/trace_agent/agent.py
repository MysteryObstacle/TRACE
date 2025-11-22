from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Optional, Tuple

from langchain_core.language_models.chat_models import BaseChatModel

from .memory import ConversationState, PlanContext, PlanStep, StepResult
from .prompting import GOAL_EXTRACTION_PROMPT, SCENE_TASK_CLASSIFIER, build_react_prompt
from .tools import Toolset


@dataclass
class AgentConfig:
    auto_execute: bool = True
    default_tools: Optional[Toolset] = None
    max_react_turns: int = 7
    stream: bool = False
    stream_handler: Optional[Callable[[str], None]] = None
    approval_callback: Optional[Callable[[PlanStep, StepResult], Tuple[bool, Optional[str]]]] = None


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
            self._run_generic_react(user_intent)
            return self.state.plan_context

        for step in self.generate_plan():
            self.state.set_current_step(step)
            for _ in range(self.config.max_react_turns):
                step_result = self._run_react_turn(step, user_intent)
                step_result, should_continue = self._confirm_step(step, step_result)
                if should_continue:
                    self.state.record_step(step, step_result)
                if not should_continue or self._step_is_complete(step_result):
                    break
        return self.state.plan_context

    def _run_generic_react(self, user_intent: str) -> list[StepResult]:
        """Run a ReAct loop for non-scene tasks without recording plan context."""

        results: list[StepResult] = []
        for _ in range(self.config.max_react_turns):
            result = self._run_react_turn(
                PlanStep.UNDERSTAND_INTENT, user_intent, extra_history=results
            )
            result, should_continue = self._confirm_step(PlanStep.UNDERSTAND_INTENT, result)
            if should_continue:
                results.append(result)
            if not should_continue or self._step_is_complete(result):
                break
        return results

    def _run_react_turn(
        self, step: PlanStep, user_intent: str, extra_history: Optional[list[StepResult]] = None
    ) -> StepResult:
        prompt = build_react_prompt(step, self.tools.tool_names())
        prompt_to_send = prompt.invoke(
            {
                "context": self._context_snippet(extra_history),
                "user_intent": user_intent,
                "topo_summary": self.state.topo_json.get("summary", "(空拓扑)"),
            }
        )
        content = self._generate_response(prompt_to_send)
        return self._parse_react_blocks(content)

    def _generate_response(self, prompt) -> str:
        if self.config.stream and hasattr(self.llm, "stream"):
            chunks: list[str] = []
            for chunk in self.llm.stream(prompt):
                piece = getattr(chunk, "content", None)
                if piece is None and hasattr(chunk, "message"):
                    piece = getattr(chunk.message, "content", "")
                piece = piece or ""
                if self.config.stream_handler and piece:
                    self.config.stream_handler(piece)
                chunks.append(piece)
            return "".join(chunks)

        response = self.llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        if self.config.stream and self.config.stream_handler:
            self.config.stream_handler(content)
        return content

    def _context_snippet(self, extra_history: Optional[list[StepResult]] = None) -> str:
        parts: list[str] = []
        for step, results in self.state.plan_context.steps.items():
            for idx, result in enumerate(results, start=1):
                parts.append(f"{step.label} #{idx}: {result.observe}")
        if extra_history:
            for idx, result in enumerate(extra_history, start=1):
                parts.append(f"当前步骤上下文 #{idx}: {result.observe}")
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

    def _confirm_step(self, step: PlanStep, result: StepResult) -> Tuple[StepResult, bool]:
        if self.config.auto_execute:
            return result, True
        if not self.config.approval_callback:
            raise ValueError("auto_execute=False requires an approval_callback to continue")

        proceed, edited_think = self.config.approval_callback(step, result)
        if edited_think:
            result = replace(result, think=edited_think)
        return result, bool(proceed)

    def _step_is_complete(self, result: StepResult) -> bool:
        text = f"{result.action} {result.observe}".lower()
        completion_markers = ["[finished]", "完成", "结束", "done", "完成本步骤", "已完成", "达成"]
        return any(marker.lower() in text for marker in completion_markers)

    def plan_outline(self) -> str:
        steps = [step.label for step in self.generate_plan()]
        return "PLAN:\n" + "\n".join(steps)

    def available_tools(self) -> str:
        return self.tools.describe()

    def provide_persistent_prompts(self, prompts: dict[str, str]) -> None:
        self.state.persistent_prompts.update(prompts)
