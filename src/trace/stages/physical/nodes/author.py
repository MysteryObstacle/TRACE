from __future__ import annotations

from pathlib import Path

from trace.stages.common import invoke_role
from trace.stages.physical.schemas import PhysicalAuthorArtifact
from trace.stages.physical.state import PhysicalState
from trace.tools.images.catalog import image_catalog_prompt
from trace.tools.tgraph.prompting import load_tgraph_contract_for


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "author.md"


def author_node(state: PhysicalState, role_client) -> PhysicalState:
    messages, artifact = invoke_role(
        role_client=role_client,
        role_name="physical_author",
        system_prompt_path=PROMPT_PATH,
        task="Author physical-stage checkpoints for the current logical graph.",
        context_sections={
            "logical_artifact": state["logical_artifact"],
            "ground_artifact": state["ground_artifact"],
        },
        system_context_sections={
            "tgraph_contract": load_tgraph_contract_for("physical_author"),
            "image_catalog": image_catalog_prompt(),
        },
        schema=PhysicalAuthorArtifact,
    )
    state["author_output"] = artifact
    state["messages"] = messages
    state["events"] = [*state.get("events", []), {"type": "physical.author.completed"}]
    return state
