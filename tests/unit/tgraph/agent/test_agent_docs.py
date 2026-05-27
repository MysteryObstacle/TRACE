from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[4] / "src" / "tgraph" / "agent" / "docs"

EXPECTED = [
    "index.md",
    "tgraph_view_api.md",
    "tgraph_check_api.md",
    "tgraph_editor_api.md",
    "fact_kinds.md",
    "checkpoint_authoring.md",
    "mutation_authoring.md",
    "repair_playbook.md",
]


@pytest.mark.parametrize("name", EXPECTED)
def test_agent_docs_exist(name: str):
    assert (DOCS / name).is_file()


def test_index_routes_to_task_docs():
    text = (DOCS / "index.md").read_text(encoding="utf-8")
    assert "tgraph_view_api.md" in text
    assert "checkpoint_authoring.md" in text
    assert "repair_playbook.md" in text


def test_checkpoint_authoring_mentions_check_chain_and_repair_target():
    text = (DOCS / "checkpoint_authoring.md").read_text(encoding="utf-8")
    assert "check_chain" in text
    assert "repair_target" in text


def test_mutation_authoring_mentions_ensure_direct_link():
    text = (DOCS / "mutation_authoring.md").read_text(encoding="utf-8")
    assert "ensure_direct_link" in text
