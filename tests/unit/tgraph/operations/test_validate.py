from tgraph import TGraph


def test_validation_issue_and_report_models_are_agent_friendly():
    from tgraph.operations.validate import ValidationIssue, ValidationReport

    warning = ValidationIssue(
        message="Heads up",
        severity="warning",
        location="nodes[0]",
        details={"issue_kind": "warn_only"},
    )
    error = ValidationIssue(message="Unknown port", details={"issue_kind": "bad_link"})

    assert warning.model_dump(mode="json") == {
        "message": "Heads up",
        "severity": "warning",
        "location": "nodes[0]",
        "details": {"issue_kind": "warn_only"},
    }
    assert ValidationReport.from_issues([warning]).ok is True
    assert ValidationReport.from_issues([warning, error]).ok is False


def test_validation_policy_defaults_to_all_levels():
    from tgraph.operations.validate import ValidationPolicy

    policy = ValidationPolicy()

    assert policy.levels == ["f1", "f2", "f3", "f4"]
    assert policy.stage is None


def test_validate_document_reports_f1_and_f2_issues():
    from tgraph import validate_document
    from tgraph.operations.validate import ValidationPolicy

    non_object = validate_document([], ValidationPolicy(levels=["f1"]))
    unknown_field = validate_document({"stage": "logical", "nodes": [], "links": [], "metadata": {}}, ValidationPolicy(levels=["f1"]))
    bad_schema = validate_document({"stage": "draft", "nodes": [{"id": "X", "type": "server", "label": "X"}], "links": []}, ValidationPolicy(levels=["f2"]))

    assert _issue_kinds(non_object) == ["document_not_object"]
    assert _issue_kinds(unknown_field) == ["unknown_top_level_field"]
    assert _issue_kinds(bad_schema) == ["schema_validation_error"]


def test_validate_graph_reports_f3_graph_consistency_issues():
    from tgraph import validate_graph
    from tgraph.operations.validate import ValidationPolicy

    graph = TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {"id": "A", "type": "router", "label": "A", "ports": [{"id": "a1"}, {"id": "a1"}]},
                {"id": "A", "type": "router", "label": "A duplicate", "ports": [{"id": "a2"}]},
                {"id": "B", "type": "computer", "label": "B", "ports": [{"id": "b1"}]},
            ],
            "links": [
                {"id": "wrong", "from_node": "A", "from_port": "a1", "to_node": "B", "to_port": "b1"},
                {"id": "a2--missing", "from_node": "A", "from_port": "a2", "to_node": "B", "to_port": "missing"},
            ],
        }
    )

    report = validate_graph(graph, ValidationPolicy(levels=["f3"]))

    assert report.ok is False
    assert {
        "duplicate_node_id",
        "duplicate_port_id",
        "noncanonical_link_id",
        "unknown_link_port",
    }.issubset(set(_issue_kinds(report)))


def test_validate_graph_f3_resolves_ports_by_node_endpoint():
    from tgraph import validate_graph
    from tgraph.operations.validate import ValidationPolicy

    graph = TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {"id": "A", "type": "computer", "label": "A", "ports": [{"id": "_B-1"}]},
                {"id": "B", "type": "switch", "label": "B", "ports": [{"id": "_A-1"}, {"id": "_C-1"}]},
                {"id": "C", "type": "computer", "label": "C", "ports": [{"id": "_B-1"}]},
            ],
            "links": [
                {"id": "A-B-1", "from_node": "A", "from_port": "_B-1", "to_node": "B", "to_port": "_A-1"},
                {"id": "B-C-1", "from_node": "C", "from_port": "_B-1", "to_node": "B", "to_port": "_C-1"},
            ],
        }
    )

    report = validate_graph(graph, ValidationPolicy(levels=["f3"]))

    assert report.ok is True
    assert report.issues == []


def test_validate_graph_reports_f4_preserve_topology_context_issues():
    from tgraph import validate_graph
    from tgraph.operations.validate import ValidationContext, ValidationPolicy

    source = TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {"id": "A", "type": "router", "label": "A", "ports": [{"id": "a1"}]},
                {"id": "B", "type": "computer", "label": "B", "ports": [{"id": "b1"}]},
            ],
            "links": [{"id": "a1--b1", "from_port": "a1", "to_port": "b1", "from_node": "A", "to_node": "B"}],
        }
    )
    candidate = TGraph.model_validate(
        {
            "stage": "physical",
            "nodes": [{"id": "A", "type": "router", "label": "A", "ports": [{"id": "a1"}]}],
            "links": [],
        }
    )

    report = validate_graph(
        candidate,
        ValidationPolicy(levels=["f4"]),
        ValidationContext(preserve_topology_from=source),
    )

    assert {"missing_preserved_node", "missing_preserved_link"}.issubset(set(_issue_kinds(report)))


def test_validate_graph_reports_f4_required_node_fields():
    from tgraph import validate_graph
    from tgraph.operations.validate import ValidationContext, ValidationPolicy

    graph = TGraph.model_validate(
        {
            "stage": "physical",
            "nodes": [{"id": "APP", "type": "computer", "label": "APP"}],
            "links": [],
        }
    )

    report = validate_graph(
        graph,
        ValidationPolicy(levels=["f4"]),
        ValidationContext(required_node_fields=["image", "flavor"]),
    )

    assert _issue_kinds(report) == ["missing_required_node_field", "missing_required_node_field"]


def test_validate_graph_with_empty_f4_context_passes():
    from tgraph import validate_graph
    from tgraph.operations.validate import ValidationContext, ValidationPolicy

    graph = TGraph.model_validate({"stage": "logical", "nodes": [], "links": []})

    report = validate_graph(graph, ValidationPolicy(levels=["f4"]), ValidationContext())

    assert report.ok is True
    assert report.issues == []


def _issue_kinds(report):
    return [issue.details.get("issue_kind") for issue in report.issues]
