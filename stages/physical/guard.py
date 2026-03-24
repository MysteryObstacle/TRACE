from stages.physical.output_schema import PhysicalOutput


def assert_valid(output: PhysicalOutput) -> None:
    if not output.physical_checkpoints:
        raise ValueError("Physical output must include at least one checkpoint.")
    if not output.tgraph_physical:
        raise ValueError("Physical output must include a physical graph payload.")
