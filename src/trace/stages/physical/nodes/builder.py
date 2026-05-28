from __future__ import annotations

from pathlib import Path
from trace.stages.common import build_messages
from trace.stages.physical.state import PhysicalState
from trace.stages.prompt_contracts import load_tgraph_contract_for
from trace.stages.repair_tools import StageRepairTools
from trace.stages.stage_results import extract_agent_messages
from trace.tools.images.catalog import catalog_summary_for_prompt


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "builder.md"
MAX_REACT_STEPS = 24


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
        mutation_index_seed=1,
    )
    messages = build_messages(
        system_prompt=PROMPT_PATH.read_text(encoding="utf-8").strip(),
        task="Build the physical graph metadata by writing and executing a mutation file.",
        context_sections={
            "constraint_files": artifact.get("constraint_files", {}),
            "checkpoint_files": artifact.get("checkpoint_files", {}),
        },
        system_context_sections={
            "tgraph_contract": load_tgraph_contract_for("physical_builder"),
            "image_catalog_summary": catalog_summary_for_prompt(node_types=["computer"]),
        },
    )
    agent_result = role_client.invoke_agent(
        role_name="physical_builder",
        messages=messages,
        tools=tools.as_agent_tools(include_checkpoint_tool=False, include_image_tools=True),
        max_react_steps=MAX_REACT_STEPS,
    )
    return {
        "draft_artifact": tools.artifact_state(),
        "support_files": tools.support_files(),
        "messages": extract_agent_messages(agent_result) or messages,
        "events": [
            {
                "type": "physical.builder.completed",
                "attempt": state["attempt"],
            }
        ],
    }
