from tgraph.operations.validate.constraint_files import (
    load_constraint_file,
    load_constraint_text,
)


def test_loads_logical_constraint_file_shape(tmp_path):
    path = tmp_path / "logical_constraints.json"
    path.write_text(
        '{"lc9": {"kind": "logical.topology.chain", "statement": "explicit chain WEB -> SW_DMZ -> R_CORE."}}',
        encoding="utf-8",
    )

    result = load_constraint_file(path, scope="logical")

    assert result.ok is True
    assert result.issues == []
    assert result.constraints["lc9"].kind == "logical.topology.chain"
    assert result.constraints["lc9"].statement == "explicit chain WEB -> SW_DMZ -> R_CORE."


def test_reports_duplicate_constraint_ids():
    result = load_constraint_text(
        '{"lc1": {"kind": "logical.topology.direct", "statement": "A -- B."},'
        '"lc1": {"kind": "logical.topology.chain", "statement": "A -> B -> C."}}',
        source="ground/logical_constraints.json",
        scope="logical",
    )

    assert result.ok is False
    assert _issue_kinds(result) == ["constraint.file.duplicate_key"]
    assert result.issues[0].details["duplicate_key"] == "lc1"
    assert result.issues[0].location == "ground/logical_constraints.json.lc1"


def test_reports_unknown_fact_kind():
    result = load_constraint_text(
        '{"lc1": {"kind": "logical.topology.dual_homed", "statement": "A has two uplinks."}}',
        source="ground/logical_constraints.json",
        scope="logical",
    )

    assert result.ok is False
    assert _issue_kinds(result) == ["constraint.kind.unknown"]
    assert result.issues[0].details["constraint_id"] == "lc1"
    assert result.issues[0].details["fact_kind"] == "logical.topology.dual_homed"


def test_reports_invalid_json():
    result = load_constraint_text(
        '{"lc1": {"kind": "physical.image.exact", "statement": "FIREWALL uses fw"}} trailing',
        source="ground/physical_constraints.json",
        scope="physical",
    )

    assert result.ok is False
    assert _issue_kinds(result) == ["constraint.file.invalid_json"]
    assert result.constraints == {}


def _issue_kinds(result):
    return [issue.details.get("issue_kind") for issue in result.issues]
