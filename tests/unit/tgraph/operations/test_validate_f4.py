from tgraph import TGraph, validate_graph
import tgraph.operations.validate.f4_intent as f4_module
from tgraph.operations.validate import CheckpointFileExecutionResult, ValidationContext, ValidationPolicy


def test_validate_graph_runs_file_backed_checkpoints(tmp_path) -> None:
    constraints_path = tmp_path / "logical_constraints.json"
    checkpoints_path = tmp_path / "checkpoints.py"
    constraints_path.write_text(
        '{"lc1": {"kind": "logical.topology.direct", "statement": "WEB is directly adjacent to SW_DMZ."}}',
        encoding="utf-8",
    )
    checkpoints_path.write_text(
        """
def check_lc1(tgraph):
    return tgraph.check_direct_link("WEB", "SW_DMZ")
""",
        encoding="utf-8",
    )
    graph = TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {"id": "WEB", "type": "computer", "label": "WEB"},
                {"id": "SW_DMZ", "type": "switch", "label": "SW_DMZ"},
            ],
            "links": [],
        }
    )

    report = validate_graph(
        graph,
        context=ValidationContext(
            constraint_files={"logical": constraints_path},
            checkpoint_files={"logical": checkpoints_path},
        ),
    )

    assert _issue_kinds(report) == ["logical.topology.direct.missing_edge"]
    assert report.issues[0].details["constraint_id"] == "lc1"


def test_tgraph_view_accepts_legacy_port_and_subnet_aliases_in_checkpoints(tmp_path) -> None:
    constraints_path = tmp_path / "logical_constraints.json"
    checkpoints_path = tmp_path / "checkpoints.py"
    constraints_path.write_text(
        '{"lc1": {"kind": "logical.custom", "statement": "WEB has an address in subnet."}}',
        encoding="utf-8",
    )
    checkpoints_path.write_text(
        """
def check_lc1(tgraph):
    ports = tgraph.get_ports("WEB")
    if not ports or not tgraph.ip_in_subnet("10.10.10.2", "10.10.10.0/24"):
        return [tgraph.issue("logical.custom", "alias failed")]
    return []
""",
        encoding="utf-8",
    )
    graph = TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [
                {
                    "id": "WEB",
                    "type": "computer",
                    "label": "WEB",
                    "ports": [{"id": "p1", "ip": "10.10.10.2", "cidr": "10.10.10.0/24"}],
                }
            ],
            "links": [],
        }
    )

    report = validate_graph(
        graph,
        context=ValidationContext(
            constraint_files={"logical": constraints_path},
            checkpoint_files={"logical": checkpoints_path},
        ),
    )

    assert report.ok is True


def test_empty_constraint_file_does_not_require_checkpoint_file(tmp_path) -> None:
    constraints_path = tmp_path / "physical_constraints.json"
    constraints_path.write_text("{}", encoding="utf-8")
    graph = TGraph.model_validate({"stage": "physical", "nodes": [], "links": []})

    report = validate_graph(
        graph,
        context=ValidationContext(constraint_files={"physical": constraints_path}),
    )

    assert report.ok is True


def test_validate_graph_preserves_physical_topology_from_logical_reference() -> None:
    logical = TGraph.model_validate(
        {
            "stage": "logical",
            "nodes": [{"id": "R1", "type": "router", "label": "R1", "ports": []}],
            "links": [],
        }
    )
    physical = TGraph.model_validate({"stage": "physical", "nodes": [], "links": []})

    report = validate_graph(
        physical,
        context=ValidationContext(preserve_topology_from=logical),
    )

    assert _has_issue_kind(report, "missing_preserved_node")


def test_validate_graph_checks_required_node_fields() -> None:
    graph = TGraph.model_validate(
        {
            "stage": "physical",
            "nodes": [{"id": "PLC1", "type": "computer", "label": "PLC1", "ports": []}],
            "links": [],
        }
    )

    report = validate_graph(graph, context=ValidationContext(required_node_fields=["image", "flavor"]))

    assert _issue_kinds(report) == ["missing_required_node_field", "missing_required_node_field"]


def test_checkpoint_file_execution_runs_scopes_serially(tmp_path, monkeypatch) -> None:
    logical_constraints = tmp_path / "logical_constraints.json"
    physical_constraints = tmp_path / "physical_constraints.json"
    logical_constraints.write_text('{"lc1": {"kind": "logical.custom", "statement": "logical"}}', encoding="utf-8")
    physical_constraints.write_text('{"pc1": {"kind": "physical.custom", "statement": "physical"}}', encoding="utf-8")
    logical_checkpoint = tmp_path / "logical_checkpoints.py"
    physical_checkpoint = tmp_path / "physical_checkpoints.py"
    logical_checkpoint.write_text("", encoding="utf-8")
    physical_checkpoint.write_text("", encoding="utf-8")

    active = 0
    max_seen = 0
    call_order: list[str] = []

    def fake_execute(_graph, *, constraints, checkpoint_path, **kwargs):
        del kwargs
        nonlocal active, max_seen
        scope = "logical" if "logical" in str(checkpoint_path) else "physical"
        call_order.append(scope)
        active += 1
        max_seen = max(max_seen, active)
        try:
            return CheckpointFileExecutionResult(ok=True, issues=[])
        finally:
            active -= 1

    monkeypatch.setattr(f4_module, "execute_checkpoint_file", fake_execute)

    report = validate_graph(
        {"stage": "logical", "nodes": [], "links": []},
        policy=ValidationPolicy(levels=["f4"]),
        context=ValidationContext(
            constraint_files={"logical": logical_constraints, "physical": physical_constraints},
            checkpoint_files={"logical": logical_checkpoint, "physical": physical_checkpoint},
        ),
    )

    assert report.ok is True
    assert max_seen == 1
    assert call_order == ["logical", "physical"]


def _issue_kinds(report):
    return [issue.details.get("issue_kind") for issue in report.issues]


def _has_issue_kind(report, issue_kind: str) -> bool:
    return issue_kind in set(_issue_kinds(report))
