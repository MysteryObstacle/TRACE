from stages.logical.output_schema import LogicalOutput


def assert_valid(output: LogicalOutput) -> None:
    if not output.logical_checkpoints:
        raise ValueError("Logical output must include at least one checkpoint.")
    if not output.tgraph_logical:
        raise ValueError("Logical output must include a logical graph payload.")
