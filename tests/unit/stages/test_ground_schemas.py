import pytest
from pydantic import ValidationError

from trace.stages.ground.schemas import GroundArtifact
from trace.stages.ground.schemas import GroundDraftArtifact
from trace.stages.ground.schemas import GroundEvaluationReport
from trace.stages.ground.schemas import NodeGroup
from trace.stages.ground.schemas import ConstraintStatement


def test_ground_evaluation_report_accepts_dict_optimizer_brief():
    report = GroundEvaluationReport(
        passed=False,
        issues=[{"code": "x", "message": "y"}],
        optimizer_brief={
            "node_groups": [{"type": "computer", "members": ["PLC1"]}],
            "logical_constraints": [{"id": "lc1", "statement": "PLC1 must connect to SWITCH1."}],
            "physical_constraints": [{"id": "pc1", "statement": "PLC1 must use image openplc-v3."}],
        },
    )

    assert report.optimizer_brief.model_dump(mode="json") == {
        "node_groups": [{"type": "computer", "members": ["PLC1"]}],
        "logical_constraints": [{"id": "lc1", "statement": "PLC1 must connect to SWITCH1."}],
        "physical_constraints": [{"id": "pc1", "statement": "PLC1 must use image openplc-v3."}],
        "notes": [],
    }


def test_ground_evaluation_report_rejects_string_optimizer_brief():
    with pytest.raises(ValidationError):
        GroundEvaluationReport(
            passed=False,
            issues=[{"code": "x", "message": "y"}],
            optimizer_brief="Define explicit node_groups and executable constraints.",
        )


def test_ground_artifact_rejects_legacy_node_group_and_constraint_shapes():
    with pytest.raises(ValidationError):
        GroundArtifact(
            node_groups=["PLC1"],
            logical_constraints=["PLC1 must connect to SWITCH1."],
        )


def test_ground_schema_descriptions_hold_output_contract_for_structured_output():
    draft_node_groups_description = GroundDraftArtifact.model_fields["node_groups"].description
    artifact_node_groups_description = GroundArtifact.model_fields["node_groups"].description

    assert "完整节点清单" in draft_node_groups_description
    assert "写入 node_groups" in draft_node_groups_description
    assert "node inventory" not in draft_node_groups_description
    assert "完整节点清单" in artifact_node_groups_description
    assert "写入 node_groups" in artifact_node_groups_description
    assert "node inventory" not in artifact_node_groups_description
    assert "logical/topology/addressing" in GroundDraftArtifact.model_fields["logical_constraints"].description
    assert "deployment/image/runtime/resource" in GroundDraftArtifact.model_fields["physical_constraints"].description
    assert "switch" in NodeGroup.model_fields["type"].description
    assert "router" in NodeGroup.model_fields["type"].description
    assert "computer" in NodeGroup.model_fields["type"].description
    assert "canonical node identifiers" in NodeGroup.model_fields["members"].description
    assert "lc1" in ConstraintStatement.model_fields["id"].description
    assert "可执行 fact" in ConstraintStatement.model_fields["statement"].description


def test_ground_artifact_rejects_extra_metadata_fields():
    with pytest.raises(ValidationError):
        GroundArtifact(
            node_groups=[{"type": "computer", "members": ["HOST1"]}],
            logical_constraints=[],
            physical_constraints=[],
            notes=["not allowed"],
        )


def test_ground_artifact_rejects_legacy_node_type_aliases():
    with pytest.raises(ValidationError):
        GroundArtifact(
            node_groups=[{"type": "host", "members": ["PLC1"]}],
            logical_constraints=[{"id": "lc1", "statement": "PLC1 must connect to SWITCH1."}],
        )


def test_ground_evaluation_report_rejects_string_issues():
    with pytest.raises(ValidationError):
        GroundEvaluationReport(
            passed=False,
            issues=["x"],
            optimizer_brief={
                "node_groups": [{"type": "computer", "members": ["PLC1"]}],
                "logical_constraints": [],
                "physical_constraints": [],
            },
        )


def test_ground_evaluation_report_rejects_legacy_issue_description_alias():
    with pytest.raises(ValidationError):
        GroundEvaluationReport(
            passed=False,
            issues=[{"description": "x"}],
            optimizer_brief={
                "node_groups": [{"type": "computer", "members": ["PLC1"]}],
                "logical_constraints": [],
                "physical_constraints": [],
            },
        )
