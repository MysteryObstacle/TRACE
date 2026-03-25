from app.contracts import ArtifactSelector, StageSpec

from stages.ground.output_schema import GroundOutput


SPEC = StageSpec(
    id="ground",
    prompt_path="prompts/ground.md",
    inputs=[
        ArtifactSelector(stage="runtime", name="intent"),
    ],
    output_model=GroundOutput.__name__,
)
