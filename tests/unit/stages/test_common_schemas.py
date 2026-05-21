import inspect

import pytest
from pydantic import ValidationError

from trace.stages.common import invoke_role
from trace.stages.common import CheckpointSpec


def test_checkpoint_spec_requires_explicit_description():
    with pytest.raises(ValidationError, match="description"):
        CheckpointSpec(
            id="cp1",
            func="connect_nodes",
            constraint_ids=["lc1"],
            args={"node_a": "A", "node_b": "B"},
        )


@pytest.mark.parametrize("args", [None, ["A", "B"], ("A", "B")])
def test_checkpoint_spec_rejects_non_dict_args(args):
    with pytest.raises(ValidationError, match="args"):
        CheckpointSpec(
            id="cp1",
            func="connect_nodes",
            description="test",
            constraint_ids=["lc1"],
            args=args,
        )


def test_checkpoint_spec_accepts_dict_args_without_rewriting():
    spec = CheckpointSpec(
        id="cp1",
        func="connect_nodes",
        description="test",
        constraint_ids=["lc1"],
        args={"node_a": "A", "node_b": "B"},
    )

    assert spec.args == {"node_a": "A", "node_b": "B"}


def test_invoke_role_signature_does_not_expose_unused_tools_argument():
    assert "tools" not in inspect.signature(invoke_role).parameters
