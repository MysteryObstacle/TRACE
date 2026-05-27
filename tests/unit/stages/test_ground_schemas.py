import pytest
from pydantic import ValidationError

from trace.stages.ground.schemas import (
    GroundArtifact,
    GroundDraftArtifact,
    GroundEvaluationReport,
    GroundIssue,
    NodeGroup,
    draft_constraints_to_file_payload,
    structural_issues_from_draft,
)


def test_ground_evaluation_report_accepts_notes_and_issue_kind():
    report = GroundEvaluationReport(
        passed=False,
        issues=[
            {
                "message": "missing node WEB",
                "location": "node_groups",
                "details": {"issue_kind": "ground.semantic.missing_node"},
            }
        ],
        notes=["add WEB to node_groups"],
    )
    assert report.passed is False
    assert report.issues[0].details["issue_kind"] == "ground.semantic.missing_node"
    assert report.notes == ["add WEB to node_groups"]


def test_ground_evaluation_report_rejects_issue_without_issue_kind():
    with pytest.raises(ValidationError):
        GroundIssue(message="x", details={})


def test_ground_artifact_uses_constraint_files_not_embedded_constraints():
    artifact = GroundArtifact(
        node_groups=[{"type": "computer", "members": ["PLC1"]}],
        constraint_files={"logical": "ground/logical_constraints.json"},
    )
    assert artifact.constraint_files["logical"] == "ground/logical_constraints.json"
    assert "logical_constraints" not in GroundArtifact.model_fields


def test_ground_artifact_rejects_legacy_node_group_and_missing_constraint_files():
    with pytest.raises(ValidationError):
        GroundArtifact(
            node_groups=["PLC1"],
            constraint_files={"logical": "ground/logical_constraints.json"},
        )

    with pytest.raises(ValidationError):
        GroundArtifact(
            node_groups=[{"type": "computer", "members": ["PLC1"]}],
            constraint_files={},
        )


def test_draft_constraints_to_file_payload():
    payload = draft_constraints_to_file_payload(
        [{"id": "lc1", "kind": "logical.topology.direct", "statement": "A connects to B."}]
    )
    assert payload == {"lc1": {"kind": "logical.topology.direct", "statement": "A connects to B."}}


def test_structural_issues_from_draft_detects_missing_kind():
    issues = structural_issues_from_draft(
        {
            "node_groups": [{"type": "switch", "members": ["SW1"]}],
            "logical_constraints": [{"id": "lc1", "statement": "missing kind"}],
            "physical_constraints": [],
        }
    )
    kinds = [issue["details"]["issue_kind"] for issue in issues]
    assert any("constraint" in kind for kind in kinds)


def test_ground_schema_descriptions_hold_output_contract_for_structured_output():
    draft_node_groups_description = GroundDraftArtifact.model_fields["node_groups"].description
    artifact_node_groups_description = GroundArtifact.model_fields["node_groups"].description

    assert "complete node inventory" in draft_node_groups_description
    assert "node_groups" in draft_node_groups_description
    assert "complete node inventory" in artifact_node_groups_description
    assert "logical_constraints.json" in GroundArtifact.model_fields["constraint_files"].description
    assert "switch" in NodeGroup.model_fields["type"].description
