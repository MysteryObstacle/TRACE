from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from tgraph.agent.protocol import playbook_paths


_AUDIENCE_PLAYBOOKS = {
    "logical_author": ("capabilities", "authoring", "validation"),
    "logical_builder": ("capabilities", "authoring", "validation"),
    "logical_repair": ("capabilities", "repair", "validation"),
    "physical_author": ("capabilities", "authoring", "validation"),
    "physical_builder": ("capabilities", "authoring", "validation"),
    "physical_repair": ("capabilities", "repair", "validation"),
}


def load_tgraph_contract_for(audience: str) -> str:
    names = _AUDIENCE_PLAYBOOKS.get(audience)
    if names is None:
        known = ", ".join(sorted(_AUDIENCE_PLAYBOOKS))
        raise KeyError(f"unknown TGraph contract audience: {audience}. Known audiences: {known}")
    sections = [_load_playbook(name) for name in names]
    index_doc = _agent_docs_index()
    if index_doc:
        sections.append("Agent documentation index:\n\n" + index_doc)
    return "\n\n".join(sections).strip()


def _agent_docs_index() -> str:
    path = Path(__file__).resolve().parents[2] / "tgraph" / "agent" / "docs" / "index.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=None)
def _load_playbook(name: str) -> str:
    path = playbook_paths()[name]
    return path.read_text(encoding="utf-8").strip()
