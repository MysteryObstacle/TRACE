from trace.runtime.escalation import (
    ESCALATION_TO_GROUND_KINDS,
    build_escalation_report,
    extract_escalation_issues,
)


def test_white_list_includes_documented_kinds():
    assert ESCALATION_TO_GROUND_KINDS == frozenset({
        "logical.escalation.constraint_conflict",
        "logical.escalation.no_satisfying_topology",
        "physical.escalation.no_satisfying_image",
        "physical.escalation.no_satisfying_flavor",
    })


def test_extract_escalation_issues_filters_by_kind():
    report = {
        "issues": [
            {"details": {"issue_kind": "logical.escalation.constraint_conflict", "summary": "A vs B"}},
            {"details": {"issue_kind": "logical.missing_link"}},
            {"details": {"issue_kind": "physical.escalation.no_satisfying_image"}},
        ]
    }
    matched = extract_escalation_issues(report)
    kinds = [item["details"]["issue_kind"] for item in matched]
    assert kinds == ["logical.escalation.constraint_conflict", "physical.escalation.no_satisfying_image"]


def test_extract_escalation_issues_empty_when_no_matches():
    report = {"issues": [{"details": {"issue_kind": "logical.missing_link"}}]}
    assert extract_escalation_issues(report) == []


def test_build_escalation_report_shape():
    report = {"issues": [{"details": {"issue_kind": "logical.escalation.constraint_conflict", "summary": "A vs B"}}]}
    partial_artifact = {"graph": {"nodes": []}}
    payload = build_escalation_report(
        stage_id="logical",
        report=report,
        partial_artifact=partial_artifact,
        attempt=3,
    )
    assert payload["source_stage"] == "logical"
    assert payload["attempt_at_escalation"] == 3
    assert payload["issues"] == report["issues"]
    assert payload["partial_artifact"] == partial_artifact
