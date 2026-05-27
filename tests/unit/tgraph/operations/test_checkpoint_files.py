from tgraph import TGraph
from tgraph.operations.validate.checkpoint_files import execute_checkpoint_file
from tgraph.operations.validate.constraint_files import ConstraintFact


def _constraints():
    return {
        "lc1": ConstraintFact(kind="logical.topology.direct", statement="WEB is directly adjacent to SW_DMZ."),
    }


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


def test_execute_checkpoint_file_runs_constraint_functions_and_enriches_issues(tmp_path) -> None:
    checkpoint_path = tmp_path / "checkpoints.py"
    checkpoint_path.write_text(
        """
def check_lc1(tgraph):
    return tgraph.check_direct_link("WEB", "SW_DMZ")
""",
        encoding="utf-8",
    )

    result = execute_checkpoint_file(
        _graph(),
        constraints=_constraints(),
        checkpoint_path=checkpoint_path,
    )

    assert result.ok is False
    assert _issue_kinds(result) == ["logical.topology.direct.missing_edge"]
    assert result.issues[0].details["constraint_id"] == "lc1"
    assert result.issues[0].details["fact_kind"] == "logical.topology.direct"
    assert result.issues[0].details["statement"] == "WEB is directly adjacent to SW_DMZ."
    assert result.issues[0].details["checkpoint_function"] == "check_lc1"
    assert result.issues[0].details["checkpoint_path"].endswith("checkpoints.py")


def test_checkpoint_file_reports_missing_and_orphan_functions(tmp_path) -> None:
    checkpoint_path = tmp_path / "checkpoints.py"
    checkpoint_path.write_text(
        """
def check_lc999(tgraph):
    return []
""",
        encoding="utf-8",
    )

    result = execute_checkpoint_file(_graph(), constraints=_constraints(), checkpoint_path=checkpoint_path)

    assert _issue_kinds(result) == [
        "checkpoint.coverage.missing_function",
        "checkpoint.coverage.orphan_function",
    ]


def test_checkpoint_file_reports_syntax_disallowed_import_and_duplicate_function(tmp_path) -> None:
    syntax_path = tmp_path / "syntax.py"
    syntax_path.write_text("def check_lc1(:\n    return []", encoding="utf-8")
    import_path = tmp_path / "import.py"
    import_path.write_text("import os\n\ndef check_lc1(tgraph):\n    return []", encoding="utf-8")
    duplicate_path = tmp_path / "duplicate.py"
    duplicate_path.write_text(
        """
def check_lc1(tgraph):
    return []

def check_lc1(tgraph):
    return []
""",
        encoding="utf-8",
    )

    assert _issue_kinds(execute_checkpoint_file(_graph(), constraints=_constraints(), checkpoint_path=syntax_path)) == ["checkpoint.file.syntax_error"]
    assert _issue_kinds(execute_checkpoint_file(_graph(), constraints=_constraints(), checkpoint_path=import_path)) == ["checkpoint.file.disallowed_import"]
    assert _issue_kinds(execute_checkpoint_file(_graph(), constraints=_constraints(), checkpoint_path=duplicate_path)) == ["checkpoint.file.duplicate_function"]


def test_checkpoint_file_allows_guarded_imports(tmp_path) -> None:
    checkpoint_path = tmp_path / "checkpoints.py"
    checkpoint_path.write_text(
        """
import ipaddress

def check_lc1(tgraph):
    ipaddress.ip_network("10.10.10.0/24")
    return []
""",
        encoding="utf-8",
    )

    result = execute_checkpoint_file(_graph(), constraints=_constraints(), checkpoint_path=checkpoint_path)

    assert result.ok is True
    assert result.issues == []


def test_checkpoint_file_reports_invalid_return_shape(tmp_path) -> None:
    checkpoint_path = tmp_path / "checkpoints.py"
    checkpoint_path.write_text(
        """
def check_lc1(tgraph):
    return 123
""",
        encoding="utf-8",
    )

    result = execute_checkpoint_file(_graph(), constraints=_constraints(), checkpoint_path=checkpoint_path)

    assert _issue_kinds(result) == ["checkpoint.return.invalid"]
    assert result.issues[0].details["constraint_id"] == "lc1"


def test_checkpoint_file_timeout_is_file_scoped(tmp_path) -> None:
    checkpoint_path = tmp_path / "checkpoints.py"
    checkpoint_path.write_text(
        """
def check_lc1(tgraph):
    while True:
        pass
""",
        encoding="utf-8",
    )

    result = execute_checkpoint_file(
        _graph(),
        constraints=_constraints(),
        checkpoint_path=checkpoint_path,
        timeout_seconds=0.5,
    )

    assert _issue_kinds(result) == ["checkpoint.execution.timeout"]
    assert result.issues[0].details["scope"] == "file"


def _issue_kinds(result):
    return [issue.details.get("issue_kind") for issue in result.issues]
