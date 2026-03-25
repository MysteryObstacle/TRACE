from app.contracts import ArtifactSelector, StageSpec

from stages.physical.output_schema import PhysicalOutput


SPEC = StageSpec(
    id="physical",
    prompt_path="prompts/physical.md",
    inputs=[
        ArtifactSelector(stage="ground", name="expanded_node_ids"),
        ArtifactSelector(stage="ground", name="physical_constraints"),
        ArtifactSelector(stage="logical", name="logical_checkpoints"),
        ArtifactSelector(stage="logical", name="tgraph_logical"),
    ],
    output_model=PhysicalOutput.__name__,
    max_rounds=5,
    repair_mode="patch",
)
