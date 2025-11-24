from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable, Optional, Tuple

from langchain.agents import AgentState, create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from .memory import ConversationState, PlanContext, PlanStep, StepResult
from .prompting import (
    GOAL_EXTRACTION_PROMPT,
    REACT_SYSTEM_PROMPT,
    SCENE_TASK_CLASSIFIER,
    build_react_prompt,
)
from .tools import Toolset


@dataclass
class AgentConfig:
    auto_execute: bool = True
    default_tools: Optional[Toolset] = None
    max_react_turns: int = 7
    # Require at least this many turns before allowing a step to finish, even if the
    # model emits completion markers early. Helps force multi-turn reasoning.
    min_react_turns: int = 2
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


class _ThinkStreamFilter:
    """Filter that suppresses <think>...</think> spans when streaming tokens."""

    def __init__(self) -> None:
        self._buffer = ""
        self._suppress = False

    def feed(self, chunk: str) -> str:
        self._buffer += chunk
        visible_parts: list[str] = []

        while self._buffer:
            if self._suppress:
                end = self._buffer.find("</think>")
                if end == -1:
                    # Still inside a <think> block, drop everything so far.
                    self._buffer = ""
                    return "".join(visible_parts)
                self._buffer = self._buffer[end + len("</think>") :]
                self._suppress = False
                continue

            start = self._buffer.find("<think>")
            if start == -1:
                visible_parts.append(self._buffer)
                self._buffer = ""
                break

            if start > 0:
                visible_parts.append(self._buffer[:start])

            self._buffer = self._buffer[start + len("<think>") :]
            self._suppress = True

        return "".join(visible_parts)


class TraceAgent:
    """TRACE agent orchestrating the PLAN + ReAct loop."""

    def __init__(self, llm: BaseChatModel, config: Optional[AgentConfig] = None) -> None:
        self.llm = llm
        self.config = config or AgentConfig()
        self.state = ConversationState()
        self.tools = self.config.default_tools or Toolset()
        self._stream_filter = _ThinkStreamFilter()
        self._lc_agent = self._build_langgraph_agent()
        self._lc_state: dict[str, Any] = {"messages": []}

    def initialize_state(self, topo_state: Optional[dict] = None) -> None:
        if topo_state:
            self.state.set_topology(topo_state)

    def _build_langgraph_agent(self):
        return create_agent(
            model=self.llm,
            tools=self.tools.as_langchain_tools(),
            system_prompt=REACT_SYSTEM_PROMPT,
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
            self._run_generic_react(user_intent)
            return self.state.plan_context

        for step in self.generate_plan():
            self.state.set_current_step(step)
            self._reset_agent_state()
            for turn in range(self.config.max_react_turns):
                self._report(f"[Step] {step.label} | 回合 {turn + 1}")
                step_result = self._run_react_turn(step, user_intent)
                step_result, should_continue = self._confirm_step(step, step_result)
                if should_continue:
                    self.state.record_step(step, step_result)
                if not should_continue or self._step_is_complete(step_result, turn):
                    break
        return self.state.plan_context

    def _run_generic_react(self, user_intent: str) -> list[StepResult]:
        """Run a ReAct loop for non-scene tasks without recording plan context."""

        results: list[StepResult] = []
        self._reset_agent_state()
        for turn in range(self.config.max_react_turns):
            self._report(f"[Step] 通用ReAct | 回合 {turn + 1}")
            result = self._run_react_turn(
                PlanStep.UNDERSTAND_INTENT, user_intent, extra_history=results
            )
            result, should_continue = self._confirm_step(PlanStep.UNDERSTAND_INTENT, result)
            if should_continue:
                results.append(result)
            if not should_continue or self._step_is_complete(result, turn):
                break
        return results

    def _run_react_turn(
        self, step: PlanStep, user_intent: str, extra_history: Optional[list[StepResult]] = None
    ) -> StepResult:
        context_text = self._context_snippet(extra_history)
        self.tools.prime_plan_context(
            context_text, user_intent=user_intent, overall_goal=self.state.overall_goal
        )

        # Prepare LangChain agent state with message history + this turn's human prompt.
        human_prompt = build_react_prompt(step, self.tools.tool_names()).format(
            context=context_text,
            user_intent=user_intent,
            topo_summary=self.state.topo_json.get("summary", "(空拓扑)"),
        )

        current_messages: list[BaseMessage] = list(self._lc_state.get("messages", []))
        current_messages.append(HumanMessage(content=human_prompt))
        base_len = len(current_messages)

        agent_state = {
            "messages": current_messages,
            "plan_context": context_text,
            "user_intent": user_intent,
            "step_label": step.label,
            "topo_summary": self.state.topo_json.get("summary", "(空拓扑)"),
        }

        result_state = self._invoke_agent(agent_state)
        self._lc_state = result_state
        return self._extract_step_result(base_len, result_state.get("messages", []))

    def _context_snippet(self, extra_history: Optional[list[StepResult]] = None) -> str:
        parts: list[str] = []
        if self.state.overall_goal:
            parts.append(f"总体目标: {self.state.overall_goal}")
        for step, results in self.state.plan_context.steps.items():
            for idx, result in enumerate(results, start=1):
                parts.append(f"{step.label} #{idx}: {result.observe}")
        if extra_history:
            for idx, result in enumerate(extra_history, start=1):
                parts.append(f"当前步骤上下文 #{idx}: {result.observe}")
        return "\n".join(parts) if parts else "(无历史上下文)"

    def _invoke_agent(self, agent_state: dict) -> dict:
        if self.config.stream and self.config.stream_handler:
            self._stream_filter = _ThinkStreamFilter()

        if self.config.stream and hasattr(self._lc_agent, "stream"):
            final_state: Optional[dict] = None
            for chunk in self._lc_agent.stream(agent_state, stream_mode="values"):
                final_state = chunk
                self._handle_stream_chunk(chunk)
            if self.config.stream_handler:
                self.config.stream_handler("\n")
            return final_state or agent_state

        return self._lc_agent.invoke(agent_state)

    def _handle_stream_chunk(self, chunk: dict) -> None:
        if not self.config.stream_handler:
            return

        messages = chunk.get("messages", [])
        if not messages:
            return
        latest = messages[-1]
        text = getattr(latest, "content", "")
        if not text:
            return
        visible = self._stream_filter.feed(text)
        if visible:
            self.config.stream_handler(visible)

    def _extract_step_result(self, base_len: int, messages: list[BaseMessage]) -> StepResult:
        think_parts: list[str] = []
        action_parts: list[str] = []
        observe_parts: list[str] = []

        for msg in messages[base_len:]:
            if isinstance(msg, AIMessage):
                if msg.tool_calls:
                    action_parts.extend(tc.get("name", "") for tc in msg.tool_calls)
                if msg.content:
                    think_parts.append(msg.content)
            elif isinstance(msg, ToolMessage):
                observe_parts.append(msg.content if hasattr(msg, "content") else str(msg))

        think = "\n".join(p for p in think_parts if p).strip() or "(无新思考)"
        action = "; ".join(a for a in action_parts if a).strip() or "N/A"
        observe = "\n".join(p for p in observe_parts if p).strip() or think
        return StepResult(think=think, action=action, observe=observe, output=None)

    def _reset_agent_state(self) -> None:
        self._lc_state = {"messages": []}

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

    def _step_is_complete(self, result: StepResult, turn_index: int) -> bool:
        """Detect completion only when explicit markers appear after minimum turns."""

        # Enforce a minimum number of turns before accepting completion to encourage
        # multi-step reasoning instead of single-shot finishing.
        if (turn_index + 1) < max(1, self.config.min_react_turns):
            return False

        text = f"{result.action} {result.observe}".lower()
        # Only respect explicit markers, reducing accidental matches from tool output.
        return "[finished]" in text

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
