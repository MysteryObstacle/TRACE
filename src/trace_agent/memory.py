from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional


class PlanStep(Enum):
    """Fixed plan steps for scene generation."""

    UNDERSTAND_INTENT = auto()
    SELECT_NODE_TYPES = auto()
    DIVIDE_ZONES = auto()
    ASSIGN_NODE_ATTRIBUTES = auto()
    GENERATE_JSON = auto()
    GENERATE_SCENEGRAPH = auto()
    VERIFY_CODE = auto()

    @property
    def label(self) -> str:
        mapping = {
            PlanStep.UNDERSTAND_INTENT: "Step 1: 理解用户意图及大致目标网络架构",
            PlanStep.SELECT_NODE_TYPES: "Step 2: 确定可能用到的节点类型",
            PlanStep.DIVIDE_ZONES: "Step 3: 划分网络区域和组",
            PlanStep.ASSIGN_NODE_ATTRIBUTES: "Step 4: 分配节点属性",
            PlanStep.GENERATE_JSON: "Step 5: 生成 JSON 表示形式",
            PlanStep.GENERATE_SCENEGRAPH: "Step 6: 从 JSON 生成 SceneGraph 代码",
            PlanStep.VERIFY_CODE: "Step 7: 验证代码（语法、SDK 一致性）",
        }
        return mapping[self]


@dataclass
class StepResult:
    """Result of a single plan step."""

    think: str
    action: str
    observe: str
    output: Optional[str] = None


@dataclass
class PlanContext:
    """Context that accumulates per-step results."""

    steps: Dict[PlanStep, List[StepResult]] = field(default_factory=dict)

    def add_result(self, step: PlanStep, result: StepResult) -> None:
        self.steps.setdefault(step, []).append(result)

    def latest_output(self, step: PlanStep) -> Optional[str]:
        if step not in self.steps or not self.steps[step]:
            return None
        return self.steps[step][-1].output


@dataclass
class ConversationState:
    """State maintained during a conversation session."""

    overall_goal: Optional[str] = None
    topo_json: Dict[str, object] = field(default_factory=dict)
    plan_context: PlanContext = field(default_factory=PlanContext)
    current_step: Optional[PlanStep] = None
    persistent_prompts: Dict[str, str] = field(default_factory=dict)

    def set_goal(self, goal: str) -> None:
        self.overall_goal = goal

    def set_topology(self, topo: Dict[str, object]) -> None:
        self.topo_json = topo

    def set_current_step(self, step: PlanStep) -> None:
        self.current_step = step

    def record_step(self, step: PlanStep, result: StepResult) -> None:
        self.plan_context.add_result(step, result)
        if step == PlanStep.GENERATE_JSON and result.output:
            self.topo_json = result.output  # type: ignore[assignment]
