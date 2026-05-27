from __future__ import annotations

from pathlib import Path
from typing import Any

from trace.stages.common import build_messages
from trace.stages.physical.state import PhysicalState
from trace.stages.prompt_contracts import load_tgraph_contract_for
from trace.stages.repair_tools import StageRepairTools


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "builder.md"
MAX_TOOL_CALLS = 24


def builder_node(state: PhysicalState, role_client) -> PhysicalState:
    artifact = {
        **state["draft_artifact"],
        "checkpoint_files": state.get("author_output", {}).get("checkpoint_files", {}),
    }
    tools = StageRepairTools(
        artifact,
        support_files=state.get("support_files", {}),
        support_file_root=state.get("support_file_root"),
        logical_reference_graph=state["logical_artifact"]["graph"],
    )
    messages = build_messages(
        system_prompt=PROMPT_PATH.read_text(encoding="utf-8").strip(),
        task="Build the physical graph metadata by writing and executing a mutation file.",
        context_sections={
            "constraint_files": artifact.get("constraint_files", {}),
            "checkpoint_files": artifact.get("checkpoint_files", {}),
        },
        system_context_sections={"tgraph_contract": load_tgraph_contract_for("physical_builder")},
    )
    agent_result = role_client.invoke_agent(
        role_name="physical_builder",
        messages=messages,
        tools=tools.as_agent_tools(include_checkpoint_tool=False, include_image_tools=True),
        max_tool_calls=MAX_TOOL_CALLS,
    )
    state["draft_artifact"] = tools.artifact_state()
    state["support_files"] = tools.support_files()
    state["messages"] = _extract_messages(agent_result) or messages
    state["events"] = [*state.get("events", []), {"type": "physical.builder.completed", "attempt": state["attempt"]}]
    return state


def _extract_messages(agent_result: Any) -> list[dict[str, Any]]:
    if isinstance(agent_result, dict):
        messages = agent_result.get("messages")
        if isinstance(messages, list):
            return [item for item in messages if isinstance(item, dict) and item.get("role")]
    return []
