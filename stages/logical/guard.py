from stages.logical.output_schema import LogicalOutput


REQUIRED_PROFILE = "logical.v1"


def assert_valid(output: LogicalOutput) -> None:
    if not output.logical_checkpoints:
        raise ValueError("Logical output must include at least one checkpoint.")
    if output.tgraph_logical and output.tgraph_logical.get("profile") != REQUIRED_PROFILE:
        raise ValueError("Logical output must use profile logical.v1.")
