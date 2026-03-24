from app.contracts import ArtifactSelector, ValidationIssue


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
