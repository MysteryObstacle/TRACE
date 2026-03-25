from __future__ import annotations

import re


COMPACT_REF_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_-]*)\[(\d+)\.\.(\d+)\]")
VAGUE_GROUP_PATTERNS = (
    re.compile(r"\ball\s+[a-z0-9_-]+\s+nodes\b", flags=re.IGNORECASE),
    re.compile(r"\ball\s+[a-z0-9_-]+\s+hosts\b", flags=re.IGNORECASE),
    re.compile(r"\bthe\s+[a-z0-9_-]+\s+devices\b", flags=re.IGNORECASE),
)
UNDER_GROUNDED_PATTERNS = (
    re.compile(r"\bdivided into\b.*\bsegments?\b", flags=re.IGNORECASE),
    re.compile(r"\bsplit into\b.*\bsegments?\b", flags=re.IGNORECASE),
    re.compile(r"\bsegmented into\b.*\bsegments?\b", flags=re.IGNORECASE),
    re.compile(r"\bfour logical subnets?\b", flags=re.IGNORECASE),
)
GRAPH_LEVEL_PATTERNS = (
    re.compile(r"\bthe whole logical topology\b", flags=re.IGNORECASE),
    re.compile(r"\bthe whole topology\b", flags=re.IGNORECASE),
    re.compile(r"\bthe entire logical topology\b", flags=re.IGNORECASE),
    re.compile(r"\bthe entire topology\b", flags=re.IGNORECASE),
)
SET_LEVEL_PATTERNS = (
    re.compile(r"\bmust use cidr\b", flags=re.IGNORECASE),
    re.compile(r"\bmust use transit cidr\b", flags=re.IGNORECASE),
    re.compile(r"\bmust be in\b.*\bsubnet\b", flags=re.IGNORECASE),
    re.compile(r"\bmust be in\b.*\bsegment\b", flags=re.IGNORECASE),
    re.compile(r"\bmust not be in the same subnet\b", flags=re.IGNORECASE),
)
RELATIONSHIP_LEVEL_PATTERNS = (
    re.compile(r"\bmust connect to\b.*\bthrough\b", flags=re.IGNORECASE),
    re.compile(r"\bmust connect to\b.*\bvia\b", flags=re.IGNORECASE),
    re.compile(r"\bmust not directly connect to\b", flags=re.IGNORECASE),
    re.compile(r"\bmust reach\b.*\bthrough\b", flags=re.IGNORECASE),
    re.compile(r"\bmust connect to\b", flags=re.IGNORECASE),
)
PHYSICAL_LEVEL_PATTERNS = (
    re.compile(r"\bmust use(?:\s+\S+){0,6}\s+image\b", flags=re.IGNORECASE),
    re.compile(r"\bmust use(?:\s+\S+){0,6}\s+model\b", flags=re.IGNORECASE),
    re.compile(r"\bmust use(?:\s+\S+){0,6}\s+flavor\b", flags=re.IGNORECASE),
)


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

    for node_id in _extract_literal_node_refs(text, available_ids):
        if node_id not in resolved:
            resolved.append(node_id)

    return resolved


def contains_vague_node_group(text: str) -> bool:
    return any(pattern.search(text) is not None for pattern in VAGUE_GROUP_PATTERNS)


def contains_under_grounded_goal(text: str) -> bool:
    return any(pattern.search(text) is not None for pattern in UNDER_GROUNDED_PATTERNS)


def classify_constraint_family(text: str, available_ids: list[str], *, is_physical: bool) -> str | None:
    if is_physical:
        refs = resolve_constraint_refs(text, available_ids)
        if refs and any(pattern.search(text) is not None for pattern in PHYSICAL_LEVEL_PATTERNS):
            return 'physical'
        return None

    if any(pattern.search(text) is not None for pattern in GRAPH_LEVEL_PATTERNS):
        return 'graph-level'

    refs = resolve_constraint_refs(text, available_ids)
    if not refs:
        return None

    if any(pattern.search(text) is not None for pattern in RELATIONSHIP_LEVEL_PATTERNS):
        return 'relationship-level'
    if any(pattern.search(text) is not None for pattern in SET_LEVEL_PATTERNS):
        return 'set-level'
    return None


def _extract_literal_node_refs(text: str, available_ids: list[str]) -> list[str]:
    refs: list[str] = []
    for node_id in sorted(available_ids, key=len, reverse=True):
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(node_id)}(?![A-Za-z0-9_])")
        if pattern.search(text):
            refs.append(node_id)
    return refs
