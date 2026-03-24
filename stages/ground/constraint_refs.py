from __future__ import annotations

import re


COMPACT_REF_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_-]*)\[(\d+)\.\.(\d+)\]")


def resolve_constraint_refs(text: str, available_ids: list[str]) -> list[str]:
    resolved: list[str] = []
    available = set(available_ids)

    for prefix, start_text, end_text in COMPACT_REF_RE.findall(text):
        start = int(start_text)
        end = int(end_text)
        width = max(len(start_text), len(end_text))
        step = 1 if start <= end else -1

        for value in range(start, end + step, step):
            node_id = f"{prefix}{value:0{width}d}" if width > 1 else f"{prefix}{value}"
            if node_id not in available:
                raise ValueError(f'constraint references unknown nodes: {node_id}')
            resolved.append(node_id)

    return resolved
