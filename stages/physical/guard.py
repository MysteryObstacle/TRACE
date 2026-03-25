from stages.physical.output_schema import PhysicalOutput


REQUIRED_PROFILE = "taal.default.v1"


def assert_valid(output: PhysicalOutput) -> None:
    if not output.physical_checkpoints:
        raise ValueError("Physical output must include at least one checkpoint.")
    if output.tgraph_physical and output.tgraph_physical.get("profile") != REQUIRED_PROFILE:
        raise ValueError("Physical output must use profile taal.default.v1.")
