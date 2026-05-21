from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path


TGRAPH_CONTRACT_PATH = Path(__file__).resolve().with_name("contract.md")
TGRAPH_CONTRACT_PARTS_DIR = Path(__file__).resolve().with_name("contracts")

_AUDIENCE_SECTIONS = {
    "logical_builder": ("core_schema", "graph_validity"),
    "logical_author": ("core_schema", "f4_checkpoint_sdk", "custom_validator_sdk"),
    "logical_repair": (
        "core_schema",
        "graph_validity",
        "f4_checkpoint_sdk",
        "custom_validator_sdk",
        "mutation_tools",
    ),
    "physical_builder": ("core_schema", "graph_validity", "physical_metadata"),
    "physical_author": ("core_schema", "f4_checkpoint_sdk", "custom_validator_sdk", "physical_metadata"),
    "physical_repair": (
        "core_schema",
        "graph_validity",
        "f4_checkpoint_sdk",
        "custom_validator_sdk",
        "mutation_tools",
        "physical_metadata",
    ),
}


def load_tgraph_contract() -> str:
    return TGRAPH_CONTRACT_PATH.read_text(encoding="utf-8").strip()


def load_tgraph_contract_for(audience: str) -> str:
    section_names = _AUDIENCE_SECTIONS.get(audience)
    if section_names is None:
        known = ", ".join(sorted(_AUDIENCE_SECTIONS))
        raise KeyError(f"unknown TGraph contract audience: {audience}. Known audiences: {known}")
    return "\n\n".join(_load_contract_part(name) for name in section_names).strip()


@lru_cache(maxsize=None)
def _load_contract_part(name: str) -> str:
    path = TGRAPH_CONTRACT_PARTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=1)
def _tool_doc_map() -> dict[str, str]:
    lines = load_tgraph_contract().splitlines()
    docs: dict[str, str] = {}
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        match = re.match(r"- `(?P<name>[a-z_]+)\([^`]*\)`", stripped)
        if match is None:
            index += 1
            continue

        name = match.group("name")
        index += 1
        bullets: list[str] = []
        while index < len(lines):
            stripped = lines[index].strip()
            if not stripped:
                index += 1
                continue
            if stripped.startswith("- `") or stripped.startswith("##") or stripped.startswith("###"):
                break
            if stripped.startswith("- "):
                bullets.append(stripped[2:].strip())
            index += 1
        if bullets:
            docs[name] = " ".join(bullets)

    return docs


def get_tgraph_tool_doc(tool_name: str) -> str:
    doc = _tool_doc_map().get(tool_name)
    if doc is None:
        raise KeyError(f"unknown TGraph tool doc: {tool_name}")
    return doc
