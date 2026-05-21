from __future__ import annotations

from pathlib import Path

from trace.stages.common import invoke_role
from trace.stages.logical.schemas import LogicalArtifact
from trace.stages.logical.state import LogicalState
from trace.tools.tgraph.prompting import load_tgraph_contract_for
from trace.tools.tgraph.runtime import TGraphRuntime


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "builder.md"


def builder_node(state: LogicalState, role_client) -> LogicalState:
    messages, artifact = invoke_role(
        role_client=role_client,
        role_name="logical_builder",
        system_prompt_path=PROMPT_PATH,
        task="Build the logical TGraphJSON artifact using the provided logical constraints and skeleton.",
        context_sections={
            "ground_artifact": state["ground_artifact"],
            "working_graph": state["working_graph"],
            "logical_constraints": state["ground_artifact"].get("logical_constraints", []),
        },
        system_context_sections={"tgraph_contract": load_tgraph_contract_for("logical_builder")},
        schema=LogicalArtifact,
    )
    tgraph_logical = TGraphRuntime.from_json(artifact["tgraph_logical"]).to_json()
    state["draft_artifact"] = {
        "tgraph_logical": tgraph_logical,
        "logical_checkpoints": state["author_output"].get("logical_checkpoints", []),
        "logical_validator_script": state["author_output"].get("logical_validator_script"),
    }
    state["messages"] = messages
    state["events"] = [
        *state.get("events", []),
        {
            "type": "logical.builder.completed",
            "attempt": state["attempt"],
        },
    ]
    return state
