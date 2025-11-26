from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable, Iterable, Optional, Tuple

from langchain.agents import AgentState, create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from .memory import ConversationState, PlanContext, PlanStep, StepResult
from .prompting import GOAL_EXTRACTION_PROMPT, SCENE_TASK_CLASSIFIER, SYSTEM_PRIMER, build_step_prompt
from .tools import Toolset


@dataclass
class AgentConfig:
    auto_execute: bool = True
    default_tools: Optional[Toolset] = None
    stream: bool = False
    stream_handler: Optional[Callable[[str], None]] = None
    progress_callback: Optional[Callable[[str], None]] = None
    approval_callback: Optional[Callable[[PlanStep, StepResult], Tuple[bool, Optional[str]]]] = None


class TraceAgentState(AgentState):
    """LangChain agent state schema, tracking extra context alongside messages."""

    plan_context: str
    user_intent: str
    step_label: str
    topo_summary: str


class TraceAgent:
    """TRACE agent orchestrating the PLAN + ReAct loop."""

    def __init__(self, llm: BaseChatModel, config: Optional[AgentConfig] = None) -> None:
        self.llm = llm
        self.config = config or AgentConfig()
        self.state = ConversationState()
        self.tools = self.config.default_tools or Toolset()
        self._lc_agent = self._build_langgraph_agent()

    def initialize_state(self, topo_state: Optional[dict] = None) -> None:
        if topo_state:
            self.state.set_topology(topo_state)

    def _build_langgraph_agent(self):
        return create_agent(
            model=self.llm,
            tools=self.tools.as_langchain_tools(),
            system_prompt=SYSTEM_PRIMER,
            state_schema=TraceAgentState,
        )

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
        goal = self.derive_goal(user_intent)
        self._report(f"[总体目标] {goal}")
        is_scene = self.is_scene_construction_goal()
        self._report(f"[任务类型] {'SceneGraph构建' if is_scene else '非SceneGraph任务'}")
        if not is_scene:
            self.state.set_current_step(PlanStep.UNDERSTAND_INTENT)
            self._run_agent_step(PlanStep.UNDERSTAND_INTENT, user_intent)
            return self.state.plan_context

        for step in self.generate_plan():
            self.state.set_current_step(step)
            self._report(f"[Step] {step.label}")
            self._run_agent_step(step, user_intent)
        return self.state.plan_context

    def _context_snippet(self) -> str:
        parts: list[str] = []
        if self.state.overall_goal:
            parts.append(f"总体目标: {self.state.overall_goal}")
        for step, results in self.state.plan_context.steps.items():
            for idx, result in enumerate(results, start=1):
                parts.append(f"{step.label} #{idx}: {result.observe}")
        return "\n".join(parts) if parts else "(无历史上下文)"

    def _run_agent_step(self, step: PlanStep, user_intent: str) -> None:
        context_text = self._context_snippet()
        self.tools.prime_plan_context(
            context_text, user_intent=user_intent, overall_goal=self.state.overall_goal
        )

        human_prompt = build_step_prompt(
            step,
            self.tools.tool_names(),
            context=context_text,
            user_intent=user_intent,
            topo_summary=self.state.topo_json.get("summary", "(空拓扑)"),
        )

        agent_state = {
            "messages": [HumanMessage(content=human_prompt)],
            "plan_context": context_text,
            "user_intent": user_intent,
            "step_label": step.label,
            "topo_summary": self.state.topo_json.get("summary", "(空拓扑)"),
        }

        result_state = self._invoke_agent(agent_state)
        for result in self._collect_step_results(result_state.get("messages", [])):
            confirmed, proceed = self._confirm_step(step, result)
            if proceed:
                self.state.record_step(step, confirmed)

    def _invoke_agent(self, agent_state: dict) -> dict:
        if self.config.stream and hasattr(self._lc_agent, "stream"):
            final_state: Optional[dict] = None
            for chunk in self._lc_agent.stream(agent_state, stream_mode="values"):
                final_state = chunk
                self._maybe_stream_chunk(chunk)
            return final_state or agent_state

        return self._lc_agent.invoke(agent_state)

    def _maybe_stream_chunk(self, chunk: dict) -> None:
        if not self.config.stream_handler:
            return

        messages = chunk.get("messages", [])
        if not messages:
            return

        latest = messages[-1]
        text = getattr(latest, "content", "")
        if text:
            self.config.stream_handler(text + "\n")

    def _collect_step_results(self, messages: Iterable[BaseMessage]) -> list[StepResult]:
        results: list[StepResult] = []
        pending_think: str = ""
        pending_actions: list[str] = []

        for msg in messages:
            if isinstance(msg, AIMessage):
                if msg.tool_calls:
                    pending_think = (msg.content or "").strip()
                    pending_actions = [tc.get("name", "") for tc in msg.tool_calls]
                else:
                    text = (msg.content or "").strip()
                    results.append(
                        StepResult(
                            think=text or "(无思考)",
                            action="N/A",
                            observe=text or "(无观测)",
                            output=None,
                        )
                    )
            elif isinstance(msg, ToolMessage):
                observe = (msg.content or "").strip()
                results.append(
                    StepResult(
                        think=pending_think or "(无思考)",
                        action="; ".join(a for a in pending_actions if a) or "N/A",
                        observe=observe or "(无观测)",
                        output=None,
                    )
                )
                pending_think = ""
                pending_actions = []

        return results

    def _confirm_step(self, step: PlanStep, result: StepResult) -> Tuple[StepResult, bool]:
        if self.config.auto_execute:
            return result, True
        if not self.config.approval_callback:
            raise ValueError("auto_execute=False requires an approval_callback to continue")

        proceed, edited_think = self.config.approval_callback(step, result)
        if edited_think:
            result = replace(result, think=edited_think)
        return result, bool(proceed)

    def _report(self, message: str) -> None:
        if self.config.progress_callback:
            self.config.progress_callback(message)

    def plan_outline(self) -> str:
        steps = [step.label for step in self.generate_plan()]
        return "PLAN:\n" + "\n".join(steps)

    def available_tools(self) -> str:
        return self.tools.describe()

    def provide_persistent_prompts(self, prompts: dict[str, str]) -> None:
        self.state.persistent_prompts.update(prompts)
