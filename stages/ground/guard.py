from stages.ground.output_schema import GroundOutput


def assert_valid(output: GroundOutput) -> None:
    if not output.node_patterns:
        raise ValueError("Ground output must include at least one node pattern.")
