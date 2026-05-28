from tgraph import TGraph
from tgraph.operations.validate.f4_intent import f4_intent
from tgraph.operations.validate.policy import ValidationContext


def test_required_node_fields_for_types_only_applies_to_matching_nodes() -> None:
    graph = TGraph.model_validate(
        {
            "stage": "physical",
            "nodes": [
                {"id": "R1", "type": "router", "label": "R1", "ports": [], "image": None, "flavor": None},
                {"id": "PC1", "type": "computer", "label": "PC1", "ports": [], "image": None, "flavor": None},
            ],
            "links": [],
        }
    )
    issues = f4_intent(
        graph,
        ValidationContext(required_node_fields_for_types={"computer": ["image", "flavor"]}),
    )
    kinds = [issue.details.get("issue_kind") for issue in issues]
    assert kinds == ["missing_required_node_field", "missing_required_node_field"]
    assert all("PC1" in issue.location for issue in issues)
    assert not any("R1" in issue.location for issue in issues)
