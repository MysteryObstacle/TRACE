from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from tgraph.agent.protocol import playbook_paths


_AUDIENCE_PLAYBOOKS = {
    "logical_author": ("capabilities", "logical_author_contract"),
    "logical_builder": ("capabilities", "logical_builder_contract"),
    "logical_repair": ("capabilities", "logical_repair_contract"),
    "physical_author": ("capabilities", "physical_author_contract"),
    "physical_builder": ("capabilities", "physical_builder_contract"),
    "physical_repair": ("capabilities", "physical_repair_contract"),
}

_AUDIENCE_DOC_LINKS: dict[str, tuple[str, ...]] = {
    "logical_author": (
        "checkpoint_authoring.md",
        "tgraph_check_api.md",
        "tgraph_view_api.md",
        "fact_kinds.md",
    ),
    "logical_builder": ("mutation_authoring.md", "tgraph_editor_api.md"),
    "logical_repair": (
        "mutation_authoring.md",
        "tgraph_editor_api.md",
        "checkpoint_authoring.md",
        "repair_playbook.md",
    ),
    "physical_author": (
        "checkpoint_authoring.md",
        "tgraph_check_api.md",
        "tgraph_view_api.md",
        "fact_kinds.md",
        "catalogs.md",
    ),
    "physical_builder": ("mutation_authoring.md", "tgraph_editor_api.md", "catalogs.md"),
    "physical_repair": (
        "mutation_authoring.md",
        "tgraph_editor_api.md",
        "checkpoint_authoring.md",
        "repair_playbook.md",
        "catalogs.md",
    ),
}


def load_tgraph_contract_for(audience: str) -> str:
    names = _AUDIENCE_PLAYBOOKS.get(audience)
    if names is None:
        known = ", ".join(sorted(_AUDIENCE_PLAYBOOKS))
        raise KeyError(f"unknown TGraph contract audience: {audience}. Known audiences: {known}")
    sections = [_load_playbook(name) for name in names]
    index_doc = _agent_docs_index_for(audience)
    if index_doc:
        sections.append("Agent documentation index:\n\n" + index_doc)
    return "\n\n".join(sections).strip()


def _agent_docs_index_for(audience: str) -> str:
    links = _AUDIENCE_DOC_LINKS.get(audience)
    if not links:
        return ""
    lines = [
        "# TGraph Agent Docs",
        "",
        "Read only the docs listed for your role:",
        "",
        "| Doc | Task |",
        "|-----|------|",
    ]
    for name in links:
        lines.append(f"| [{name}]({name}) | see file |")
    return "\n".join(lines)


@lru_cache(maxsize=None)
def _load_playbook(name: str) -> str:
    path = playbook_paths()[name]
    return path.read_text(encoding="utf-8").strip()
