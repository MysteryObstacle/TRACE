from stages.ground.normalize import expand_node_patterns


def test_expand_node_patterns_handles_ranges_and_literals() -> None:
    result = expand_node_patterns(["PLC[1..3]", "HMI1"])

    assert result == ["PLC1", "PLC2", "PLC3", "HMI1"]
