import re

_RANGE_PATTERN = re.compile(r"^(?P<prefix>[A-Za-z_][A-Za-z0-9_]*?)\[(?P<start>\d+)\.\.(?P<end>\d+)\]$")


def expand_node_patterns(patterns: list[str]) -> list[str]:
    expanded: list[str] = []
    for pattern in patterns:
        match = _RANGE_PATTERN.match(pattern)
        if not match:
            expanded.append(pattern)
            continue

        prefix = match.group("prefix")
        start = int(match.group("start"))
        end = int(match.group("end"))
        if end < start:
            raise ValueError(f"Invalid node range: {pattern}")

        expanded.extend(f"{prefix}{index}" for index in range(start, end + 1))

    return expanded
