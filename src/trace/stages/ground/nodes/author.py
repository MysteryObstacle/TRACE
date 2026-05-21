from __future__ import annotations

from pathlib import Path

from trace.stages.common import invoke_role
from trace.stages.ground.schemas import GroundDraftArtifact
from trace.stages.ground.state import GroundState


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "author.md"


def _report_passed(report) -> bool:
    if report is None:
        return False
    if isinstance(report, dict):
        return bool(report.get("passed", False))
    return bool(getattr(report, "passed", False))


def author_node(state: GroundState, role_client) -> GroundState:
    report = state.get("evaluation_report")
    revising = bool(report) and not _report_passed(report)
    author_mode = "feedback_revision" if revising else "initial_draft"

    context_sections = {
        "author_mode": author_mode,
        "intent": state["intent"],
    }

    if revising:
        context_sections["evaluation_feedback"] = report
        context_sections["previous_artifact"] = state.get("draft_artifact")
        task = (
            "当前任务模式：`feedback_revision`。\n"
            "根据 `evaluation_feedback` 修订 `previous_artifact`，输出包含所有字段的完整 "
            "`GroundDraftArtifact`，禁止输出 delta patch。\n"
            "如果 evaluation_feedback 包含非空 optimizer_brief，优先使用 optimizer_brief "
            "作为修订建议；但不得盲目用 optimizer_brief 替换 previous_artifact。\n"
            "只修改 feedback 指出的错误、遗漏、冲突或不清晰事实。\n"
            "保留 previous_artifact 中未被 feedback 影响的 node_groups、logical_constraints "
            "和 physical_constraints。\n"
            "禁止重新设计整个 artifact，除非 evaluation_feedback 明确要求。"
        )
    else:
        task = (
            "当前任务模式：`initial_draft`。\n"
            "根据 `intent` 生成完整 `GroundDraftArtifact`。\n"
            "如果 intent 明确给出 fixed node IDs、CIDRs、link chains、fixed addresses "
            "或 node types，必须保守镜像这些固定事实，不得改名、合并或省略。\n"
            "如果 intent 是开放式设计需求，则生成最小、合理、可部署的 canonical "
            "node_groups、logical_constraints 和 physical_constraints。\n"
            "physical_constraints 只能来自两类证据：用户显式的 deployment、image、runtime、flavor "
            "或 resource 要求；以及开放式 archetype 中由 author 主动引入的 functional role nodes。"
            "不要仅根据节点名称推断 physical constraint。"
        )

    messages, artifact = invoke_role(
        role_client=role_client,
        role_name="ground_author",
        system_prompt_path=PROMPT_PATH,
        task=task,
        context_sections=context_sections,
        schema=GroundDraftArtifact,
    )

    state["messages"] = messages
    state["draft_artifact"] = artifact
    state["status"] = "evaluating"
    state["events"] = [
        *state.get("events", []),
        {"type": "ground.author.completed", "revision": revising},
    ]
    return state
