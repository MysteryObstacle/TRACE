from __future__ import annotations

from pathlib import Path

from trace.stages.common import invoke_role
from trace.stages.logical.schemas import LogicalAuthorArtifact
from trace.stages.logical.state import LogicalState
from trace.tools.tgraph.prompting import load_tgraph_contract_for


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "author.md"


def author_node(state: LogicalState, role_client) -> LogicalState:
    messages, artifact = invoke_role(
        role_client=role_client,
        role_name="logical_author",
        system_prompt_path=PROMPT_PATH,
        task="Author logical-stage checkpoints for the current topology problem.",
        context_sections={
            "ground_artifact": state["ground_artifact"],
        },
        system_context_sections={"tgraph_contract": load_tgraph_contract_for("logical_author")},
        schema=LogicalAuthorArtifact,
    )
    state["author_output"] = artifact
    state["messages"] = messages
    state["events"] = [*state.get("events", []), {"type": "logical.author.completed"}]
    return state
