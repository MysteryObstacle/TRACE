from __future__ import annotations

from pathlib import Path
from typing import Any

from langgraph.types import Command

from trace.runtime.escalation import build_escalation_report, extract_escalation_issues
from trace.stages.ground.schemas import PHYSICAL_CONSTRAINTS_PATH
from trace.stages.physical.state import PhysicalState
from trace.stages.prompt_contracts import load_tgraph_contract_for
from trace.stages.repair_ledger import (
    build_repair_ledger_entry as _build_repair_ledger_entry,
    extract_tool_attempts as _extract_tool_attempts,
    format_section as _format_section,
    summarize_recent_repair_ledger as _summarize_recent_repair_ledger,
)
from trace.stages.repair_tools import StageRepairTools
from trace.stages.stage_results import extract_agent_messages as _extract_messages
from trace.stages.support_files import load_constraint_entries
from trace.tools.images.catalog import catalog_summary_for_prompt


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "repair.md"
MAX_REACT_STEPS = 12


def repair_node(state: PhysicalState, role_client) -> Command:
    escalation_issues = extract_escalation_issues(state["evaluation_report"])
    if escalation_issues:
        return Command(
            goto="escalate",
            update={
                "escalation_report": build_escalation_report(
                    stage_id="physical",
                    report=state["evaluation_report"],
                    partial_artifact=state.get("draft_artifact"),
                    attempt=state["attempt"],
                )
            },
        )

    prior_ledger = list(state.get("repair_history", []))
    repair_tools = StageRepairTools(
        state["draft_artifact"],
        support_files=state.get("support_files", {}),
        support_file_root=state.get("support_file_root"),
        logical_reference_graph=state["logical_artifact"]["graph"],
        mutation_index_seed=len(prior_ledger) + 2,
    )
    messages = _build_repair_messages(
        system_prompt=PROMPT_PATH.read_text(encoding="utf-8").strip(),
        tgraph_contract=load_tgraph_contract_for("physical_repair"),
        evaluation_report=state["evaluation_report"],
        current_topology=repair_tools.inspect_graph(view="summary"),
        logical_topology=state["logical_artifact"]["graph"],
        physical_constraints=load_constraint_entries(
            support_files=state.get("support_files", {}),
            constraint_files=state["draft_artifact"].get("constraint_files", {})
            or state.get("ground_artifact", {}).get("constraint_files", {}),
            scope="physical",
            default_path=PHYSICAL_CONSTRAINTS_PATH,
        ),
        constraint_files=state["draft_artifact"].get("constraint_files", {}),
        checkpoint_files=state["draft_artifact"].get("checkpoint_files", {}),
        recent_repair_ledger=_summarize_recent_repair_ledger(prior_ledger),
    )

    agent_result = role_client.invoke_agent(
        role_name="physical_repair",
        messages=messages,
        tools=repair_tools.as_agent_tools(include_image_tools=True),
        max_react_steps=MAX_REACT_STEPS,
    )

    ledger_entry = _build_repair_ledger_entry(
        round_index=len(prior_ledger) + 1,
        issues_before=state["evaluation_report"],
        issues_after=None,
        attempted_actions=_extract_tool_attempts(agent_result),
    )
    next_attempt = state["attempt"] + 1

    return Command(
        goto="validator",
        update={
            "draft_artifact": repair_tools.artifact_state(),
            "support_files": repair_tools.support_files(),
            "messages": _extract_messages(agent_result),
            "attempt": next_attempt,
            "repair_history": [ledger_entry],
            "events": [{"type": "physical.repair.completed", "attempt": next_attempt}],
        },
    )


def _build_repair_messages(
    *,
    system_prompt: str,
    tgraph_contract: str,
    evaluation_report: dict[str, Any],
    current_topology: dict[str, Any],
    logical_topology: dict[str, Any],
    physical_constraints: list[dict[str, Any]],
    constraint_files: dict[str, str],
    checkpoint_files: dict[str, str],
    recent_repair_ledger: list[dict[str, Any]],
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": "TGraph contract for this repair round:\n\n" + tgraph_contract},
        {
            "role": "system",
            "content": "Image catalog summary for this repair round:\n\n"
            + catalog_summary_for_prompt(node_types=["computer"]),
        },
        {"role": "human", "content": "Use file-backed TGraph tools to repair the physical artifact while preserving logical topology."},
        {"role": "human", "content": _format_section("evaluation_report", evaluation_report)},
        {"role": "human", "content": _format_section("evaluation_report_is_latest", True)},
        {"role": "human", "content": _format_section("current_topology", current_topology)},
        {"role": "human", "content": _format_section("logical_topology", logical_topology)},
        {"role": "human", "content": _format_section("physical_constraints", physical_constraints)},
        {"role": "human", "content": _format_section("constraint_files", constraint_files)},
        {"role": "human", "content": _format_section("checkpoint_files", checkpoint_files)},
        {
            "role": "human",
            "content": _format_section(
                "repair_file_guidance",
                {
                    "graph_mutation": "write physical/mutations/attempt_N.py with mutate(tgraph), then execute_mutation_file.",
                    "checkpoint_repair": "read and rewrite physical/checkpoints.py only when the issue is in the checkpoint function.",
                    "image_flavor": "choose image/flavor from catalog context and set them through mutation code.",
                },
            ),
        },
        {"role": "human", "content": _format_section("recent_repair_ledger", recent_repair_ledger)},
    ]
