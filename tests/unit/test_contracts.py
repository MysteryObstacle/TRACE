from app.contracts import ArtifactSelector, FailureType, StageMode, ValidationIssue


def test_artifact_selector_round_trips() -> None:
    selector = ArtifactSelector(stage="ground", name="expanded_node_ids")

    payload = selector.model_dump()

    assert payload["stage"] == "ground"
    assert payload["name"] == "expanded_node_ids"
    assert payload["required"] is True


def test_validation_issue_defaults_are_stable() -> None:
    issue = ValidationIssue(
        code="schema_error",
        message="missing node",
        severity="error",
        scope="topology",
    )

    assert issue.targets == []
    assert issue.json_paths == []


def test_validation_issue_accepts_tgraph_scopes() -> None:
    issue = ValidationIssue(
        code="duplicate_port_id",
        message="port id duplicated",
        severity="error",
        scope="port",
    )

    assert issue.scope == "port"
    assert issue.targets == []
    assert issue.json_paths == []


def test_validation_issue_normalizes_plural_scope_aliases() -> None:
    issue = ValidationIssue(
        code="wrong_node_type",
        message="node type mismatch",
        severity="error",
        scope="nodes",
    )

    assert issue.scope == "node"


def test_failure_type_values_are_stable() -> None:
    assert FailureType.STAGE_BOUNDARY_ERROR.value == "stage_boundary_error"


def test_stage_mode_values_are_stable() -> None:
    assert StageMode.REPAIR.value == "repair"
