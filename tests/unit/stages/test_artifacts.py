import pytest
from pydantic import ValidationError

from trace.stages.logical.schemas import LogicalArtifact, LogicalAuthorArtifact
from trace.stages.physical.schemas import PhysicalArtifact, PhysicalAuthorArtifact


def test_logical_author_artifact_uses_checkpoint_file_refs() -> None:
    assert "checkpoint_files" in LogicalAuthorArtifact.model_fields
    assert "constraint_scripts" not in LogicalAuthorArtifact.model_fields
    assert "checkpoints" not in LogicalAuthorArtifact.model_fields
    assert "validator_script" not in LogicalAuthorArtifact.model_fields
    assert "logical_checkpoints" not in LogicalAuthorArtifact.model_fields


def test_physical_author_artifact_uses_checkpoint_file_refs() -> None:
    assert "checkpoint_files" in PhysicalAuthorArtifact.model_fields
    assert "checkpoints" not in PhysicalAuthorArtifact.model_fields
    assert "validator_script" not in PhysicalAuthorArtifact.model_fields
    assert "physical_checkpoints" not in PhysicalAuthorArtifact.model_fields


def test_logical_artifact_uses_file_backed_validation_refs() -> None:
    assert "graph" in LogicalArtifact.model_fields
    assert "constraint_files" in LogicalArtifact.model_fields
    assert "checkpoint_files" in LogicalArtifact.model_fields
    assert "constraint_scripts" not in LogicalArtifact.model_fields
    assert "checkpoints" not in LogicalArtifact.model_fields
    assert "validator_script" not in LogicalArtifact.model_fields
    assert "tgraph_logical" not in LogicalArtifact.model_fields


def test_physical_artifact_rejects_wrong_stage() -> None:
    with pytest.raises(ValidationError):
        PhysicalArtifact.model_validate(
            {
                "graph": {"stage": "logical", "nodes": [], "links": []},
                "constraint_files": {"physical": "ground/physical_constraints.json"},
                "checkpoint_files": {"physical": "physical/checkpoints.py"},
            }
        )
