from __future__ import annotations

from pathlib import Path

from trace.stages.common import invoke_role
from trace.stages.physical.schemas import PhysicalArtifact
from trace.stages.physical.state import PhysicalState
from trace.tools.images.catalog import image_catalog_prompt
from trace.tools.tgraph.prompting import load_tgraph_contract_for
from trace.tools.tgraph.runtime import TGraphRuntime


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "builder.md"


def builder_node(state: PhysicalState, role_client) -> PhysicalState:
    messages, artifact = invoke_role(
        role_client=role_client,
        role_name="physical_builder",
        system_prompt_path=PROMPT_PATH,
        task="Enrich the logical TGraphJSON artifact with physical deployment fields while preserving topology.",
        context_sections={
            "logical_artifact": state["logical_artifact"],
            "ground_artifact": state["ground_artifact"],
            "working_graph": state["working_graph"],
            "physical_checkpoints": state["author_output"]["physical_checkpoints"],
        },
        system_context_sections={
            "tgraph_contract": load_tgraph_contract_for("physical_builder"),
            "image_catalog": image_catalog_prompt(),
        },
        schema=PhysicalArtifact,
    )
    state["draft_artifact"] = {
        "physical_checkpoints": artifact.get("physical_checkpoints") or state["author_output"]["physical_checkpoints"],
        "physical_validator_script": (
            artifact.get("physical_validator_script")
            if artifact.get("physical_validator_script") is not None
            else state["author_output"].get("physical_validator_script")
        ),
        "tgraph_physical": TGraphRuntime.from_json(artifact["tgraph_physical"]).to_json(),
    }
    state["messages"] = messages
    state["events"] = [*state.get("events", []), {"type": "physical.builder.completed", "attempt": state["attempt"]}]
    return state
