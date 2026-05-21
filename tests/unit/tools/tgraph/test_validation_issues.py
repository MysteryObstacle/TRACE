from trace.tools.tgraph.validate import run_default_validators
from trace.tools.tgraph.validate.issues import issue
from trace.tools.tgraph.validate.types import ValidationIssue


def test_validation_issue_accepts_provenance_and_has_no_scope():
    item = ValidationIssue.model_validate(
        {
            "code": "missing_required_link",
            "message": "A is not directly connected to B",
            "severity": "error",
            "targets": ["A", "B"],
            "json_paths": [],
            "provenance": {
                "layer": "f4",
                "source": "authored_check",
                "check_id": "cp1",
                "constraint_ids": ["lc1"],
                "func": "connect_nodes",
                "impl_source": "sdk",
                "args": {"node_a": "A", "node_b": "B"},
            },
        }
    )

    assert item.provenance is not None
    assert item.provenance.check_id == "cp1"
    assert not hasattr(item, "scope")


def test_issue_helper_emits_shape_without_scope():
    payload = issue(
        "runtime_error",
        "boom",
        targets=["node:r1"],
        provenance={"layer": "f3", "source": "builtin"},
    )

    assert "scope" not in payload
    assert payload["provenance"]["layer"] == "f3"


def test_f4_sdk_failure_includes_checkpoint_provenance():
    report = run_default_validators(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "A", "type": "router", "label": "A", "ports": [], "image": None, "flavor": None},
                {"id": "B", "type": "router", "label": "B", "ports": [], "image": None, "flavor": None},
            ],
            "links": [],
        },
        logical_checkpoints=[
            {
                "id": "cp1",
                "func": "connect_nodes",
                "description": "A connect B",
                "constraint_ids": ["lc1"],
                "args": {"node_a": "A", "node_b": "B"},
            }
        ],
        logical_validator_script=None,
    ).model_dump(mode="json")

    issue_item = next(item for item in report["issues"] if item["code"] == "missing_required_link")
    assert issue_item["provenance"] == {
        "layer": "f4",
        "source": "authored_check",
        "check_id": "cp1",
        "constraint_ids": ["lc1"],
        "func": "connect_nodes",
        "impl_source": "sdk",
        "args": {"node_a": "A", "node_b": "B"},
        "artifact": None,
    }


def test_f4_script_load_failure_points_to_validator_script_artifact():
    report = run_default_validators(
        {
            "profile": "logical.v1",
            "nodes": [],
            "links": [],
        },
        logical_checkpoints=[
            {
                "id": "cp1",
                "func": "check_rule",
                "description": "broken custom script",
                "constraint_ids": ["lc1"],
                "args": {},
            }
        ],
        logical_validator_script="def check_rule(tgraph, **kwargs):\n    return [\n",
    ).model_dump(mode="json")

    issue_item = next(item for item in report["issues"] if item["code"] == "checkpoint_script_syntax_error")
    assert issue_item["provenance"] == {
        "layer": "f4",
        "source": "authored_check",
        "check_id": None,
        "constraint_ids": [],
        "func": None,
        "impl_source": "custom",
        "args": None,
        "artifact": "logical_validator_script",
    }


def test_f4_unknown_function_marks_impl_source_unknown():
    report = run_default_validators(
        {
            "profile": "logical.v1",
            "nodes": [],
            "links": [],
        },
        logical_checkpoints=[
            {
                "id": "cp3",
                "func": "check_unknown_rule",
                "description": "unknown custom check",
                "constraint_ids": ["lc3"],
                "args": {"node_id": "HOST1"},
            }
        ],
        logical_validator_script=None,
    ).model_dump(mode="json")

    issue_item = next(item for item in report["issues"] if item["code"] == "checkpoint_function_missing")
    assert issue_item["provenance"] == {
        "layer": "f4",
        "source": "authored_check",
        "check_id": "cp3",
        "constraint_ids": ["lc3"],
        "func": "check_unknown_rule",
        "impl_source": "unknown",
        "args": {"node_id": "HOST1"},
        "artifact": None,
    }


def test_f4_reports_missing_checkpoint_coverage_for_declared_constraints():
    report = run_default_validators(
        {
            "profile": "logical.v1",
            "nodes": [],
            "links": [],
        },
        logical_constraints=[
            {"id": "lc1", "statement": "A must connect to B."},
            {"id": "lc2", "statement": "B must connect to C."},
        ],
        logical_checkpoints=[],
        logical_validator_script=None,
    ).model_dump(mode="json")

    issues = [item for item in report["issues"] if item["code"] == "checkpoint_coverage_missing"]
    assert [item["provenance"]["constraint_ids"] for item in issues] == [["lc1"], ["lc2"]]
    assert all("缺少覆盖该约束的 checkpoint" in item["message"] for item in issues)


def test_f4_reports_unknown_checkpoint_constraint_ids():
    report = run_default_validators(
        {
            "profile": "logical.v1",
            "nodes": [],
            "links": [],
        },
        logical_constraints=[{"id": "lc1", "statement": "A must connect to B."}],
        logical_checkpoints=[
            {
                "id": "cp1",
                "func": "connect_nodes",
                "description": "A connect B",
                "constraint_ids": ["lc_missing"],
                "args": {"node_a": "A", "node_b": "B"},
            }
        ],
        logical_validator_script=None,
    ).model_dump(mode="json")

    issue_item = next(item for item in report["issues"] if item["code"] == "checkpoint_constraint_unknown")
    assert issue_item["message"] == "checkpoint references unknown constraint id 'lc_missing'"
    assert issue_item["provenance"]["check_id"] == "cp1"
    assert issue_item["provenance"]["constraint_ids"] == ["lc_missing"]


def test_f4_custom_function_runtime_error_names_exception_type():
    report = run_default_validators(
        {
            "profile": "logical.v1",
            "nodes": [],
            "links": [],
        },
        logical_checkpoints=[
            {
                "id": "cp1",
                "func": "check_broken",
                "description": "broken custom check",
                "constraint_ids": ["lc1"],
                "args": {"node_id": "A"},
            }
        ],
        logical_validator_script="def check_broken(tgraph, **kwargs):\n    raise KeyError('boom')\n",
    ).model_dump(mode="json")

    issue_item = next(item for item in report["issues"] if item["code"] == "checkpoint_function_runtime_error")
    assert "KeyError" in issue_item["message"]
    assert "check_broken" in issue_item["message"]
    assert issue_item["provenance"]["args"] == {"node_id": "A"}


def test_f4_custom_script_supports_type_and_isinstance_checks():
    report = run_default_validators(
        {
            "profile": "logical.v1",
            "nodes": [],
            "links": [],
        },
        logical_checkpoints=[
            {
                "id": "cp1",
                "func": "check_type_surface",
                "description": "type helpers are available",
                "constraint_ids": ["lc1"],
                "args": {},
            }
        ],
        logical_validator_script=(
            "def check_type_surface(tgraph, **kwargs):\n"
            "    if type(tgraph.nodes) is list and isinstance(tgraph.links, list):\n"
            "        return []\n"
            "    return [issue('type_surface_missing', 'type helpers are unavailable')]\n"
        ),
    )

    assert report.ok is True
