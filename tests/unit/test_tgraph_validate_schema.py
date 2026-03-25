from tools.tgraph.validate.f1_format import f1_format
from tools.tgraph.validate.f2_schema import f2_schema


def test_f1_format_requires_profile_nodes_and_links() -> None:
    issues = f1_format({"nodes": []})

    assert issues[0]["code"] == "missing_top_level_field"


def test_f2_schema_allows_null_image_and_flavor_in_logical_profile() -> None:
    issues = f2_schema(
        {
            "profile": "logical.v1",
            "nodes": [
                {
                    "id": "PC1",
                    "type": "computer",
                    "label": "PC1",
                    "ports": [],
                    "image": None,
                    "flavor": None,
                }
            ],
            "links": [],
        }
    )

    assert issues == []


def test_f2_schema_requires_computer_image_and_flavor_in_taal_profile() -> None:
    issues = f2_schema(
        {
            "profile": "taal.default.v1",
            "nodes": [
                {
                    "id": "PC1",
                    "type": "computer",
                    "label": "PC1",
                    "ports": [],
                    "image": None,
                    "flavor": None,
                }
            ],
            "links": [],
        }
    )

    assert {issue["code"] for issue in issues} >= {"computer_image_required", "computer_flavor_required"}
