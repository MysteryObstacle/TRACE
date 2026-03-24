from app.contracts import StageSpec

from stages.ground.output_schema import GroundOutput


SPEC = StageSpec(
    id="ground",
    prompt_path="prompts/ground.md",
    output_model=GroundOutput.__name__,
)
