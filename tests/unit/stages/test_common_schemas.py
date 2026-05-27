import inspect

from trace.stages.common import invoke_role


def test_invoke_role_signature_does_not_expose_unused_tools_argument():
    assert "tools" not in inspect.signature(invoke_role).parameters
