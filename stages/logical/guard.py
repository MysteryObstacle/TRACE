from stages.logical.output_schema import LogicalOutput


REQUIRED_PROFILE = "logical.v1"


def assert_valid(output: LogicalOutput) -> None:
    if not output.logical_checkpoints:
        raise ValueError("Logical output must include at least one checkpoint.")
    if not output.tgraph_logical and not output.logical_patch_ops:
        raise ValueError("Logical output must include a logical graph payload or patch ops.")
    if output.tgraph_logical and output.tgraph_logical.get("profile") != REQUIRED_PROFILE:
        raise ValueError("Logical output must use profile logical.v1.")
