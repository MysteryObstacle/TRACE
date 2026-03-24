from app.contracts import ArtifactSelector, StageSpec

from stages.logical.output_schema import LogicalOutput


SPEC = StageSpec(
    id="logical",
    prompt_path="prompts/logical.md",
    inputs=[
        ArtifactSelector(stage="ground", name="expanded_node_ids"),
        ArtifactSelector(stage="ground", name="logical_constraints"),
    ],
    output_model=LogicalOutput.__name__,
    max_rounds=3,
    repair_mode="patch",
)
