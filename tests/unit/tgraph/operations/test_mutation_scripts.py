from tgraph import TGraph
from tgraph.operations.mutate.scripts import execute_mutation_file


def _graph() -> TGraph:
    return TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {"id": "WEB", "type": "computer", "label": "WEB"},
                {"id": "SW_DMZ", "type": "switch", "label": "SW_DMZ"},
            ],
            "links": [],
        }
    )


def test_mutation_file_commits_successful_editor_changes(tmp_path) -> None:
    mutation_path = tmp_path / "attempt_1.py"
    mutation_path.write_text(
        """
def mutate(tgraph):
    tgraph.ensure_direct_link("WEB", "SW_DMZ")
""",
        encoding="utf-8",
    )

    result = execute_mutation_file(_graph(), mutation_path=mutation_path)

    assert result.ok is True
    assert [link.id for link in result.graph.links] == ["SW_DMZ-WEB-1"]
    assert result.operations[0]["op"] == "ensure_direct_link"


def test_mutation_file_runtime_exception_does_not_commit(tmp_path) -> None:
    original = _graph()
    mutation_path = tmp_path / "attempt_1.py"
    mutation_path.write_text(
        """
def mutate(tgraph):
    tgraph.ensure_direct_link("WEB", "SW_DMZ")
    raise RuntimeError("boom")
""",
        encoding="utf-8",
    )

    result = execute_mutation_file(original, mutation_path=mutation_path)

    assert result.ok is False
    assert result.graph is None
    assert original.links == []
    assert _issue_kinds(result) == ["mutation.execution.exception"]


def test_mutation_file_blocks_disallowed_import(tmp_path) -> None:
    mutation_path = tmp_path / "attempt_1.py"
    mutation_path.write_text("import os\n\ndef mutate(tgraph):\n    return None", encoding="utf-8")

    result = execute_mutation_file(_graph(), mutation_path=mutation_path)

    assert result.ok is False
    assert _issue_kinds(result) == ["mutation.file.disallowed_import"]


def test_mutation_file_timeout_does_not_commit(tmp_path) -> None:
    mutation_path = tmp_path / "attempt_1.py"
    mutation_path.write_text(
        """
def mutate(tgraph):
    while True:
        pass
""",
        encoding="utf-8",
    )

    result = execute_mutation_file(_graph(), mutation_path=mutation_path, timeout_seconds=0.5)

    assert result.ok is False
    assert result.graph is None
    assert _issue_kinds(result) == ["mutation.execution.timeout"]
    assert result.issues[0].details["scope"] == "file"


def test_mutation_file_validation_failure_does_not_commit(tmp_path) -> None:
    mutation_path = tmp_path / "attempt_1.py"
    mutation_path.write_text(
        """
def mutate(tgraph):
    tgraph.ensure_node("BAD-NODE")
""",
        encoding="utf-8",
    )

    result = execute_mutation_file(_graph(), mutation_path=mutation_path)

    assert result.ok is False
    assert result.graph is None
    assert _issue_kinds(result) == ["mutation.execution.exception"]


def test_spawn_path_returns_graph_payload(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("TGRAPH_EXECUTION_MODE", raising=False)
    mutation_path = tmp_path / "attempt_1.py"
    mutation_path.write_text(
        """
def mutate(tgraph):
    tgraph.ensure_direct_link("WEB", "SW_DMZ")
""",
        encoding="utf-8",
    )

    result = execute_mutation_file(_graph(), mutation_path=mutation_path, timeout_seconds=5.0)

    assert result.ok is True
    assert result.graph is not None
    assert [link.id for link in result.graph.links] == ["SW_DMZ-WEB-1"]


def _issue_kinds(result):
    return [issue.details.get("issue_kind") for issue in result.issues]
