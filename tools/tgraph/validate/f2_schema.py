from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from tools.tgraph.model import LOGICAL_V1, SUPPORTED_PROFILES, TAAL_DEFAULT_V1, TGraph
from tools.tgraph.validate.issues import issue


def f2_schema(tgraph: dict[str, Any], **_: Any) -> list[dict[str, Any]]:
    profile = tgraph.get("profile")
    if profile not in SUPPORTED_PROFILES:
        return [issue("unsupported_profile", f"unsupported profile '{profile}'", "topology", json_paths=["$.profile"])]

    try:
        graph = TGraph.model_validate(tgraph)
    except ValidationError as exc:
        return [_validation_error_to_issue(error) for error in exc.errors()]

    issues: list[dict[str, Any]] = []
    if profile == LOGICAL_V1:
        return issues

    if profile == TAAL_DEFAULT_V1:
        for index, node in enumerate(graph.nodes):
            target = [f"node:{node.id}"]
            if node.type == "computer":
                if node.image is None:
                    issues.append(issue("computer_image_required", "computer nodes require image metadata", "node", targets=target, json_paths=[f"$.nodes[{index}].image"]))
                if node.flavor is None:
                    issues.append(issue("computer_flavor_required", "computer nodes require flavor metadata", "node", targets=target, json_paths=[f"$.nodes[{index}].flavor"]))
            else:
                if node.image is not None:
                    issues.append(issue("non_computer_image_forbidden", "non-computer nodes must not define image metadata", "node", targets=target, json_paths=[f"$.nodes[{index}].image"]))
                if node.flavor is not None:
                    issues.append(issue("non_computer_flavor_forbidden", "non-computer nodes must not define flavor metadata", "node", targets=target, json_paths=[f"$.nodes[{index}].flavor"]))

    return issues


def _validation_error_to_issue(error: dict[str, Any]) -> dict[str, Any]:
    location = error.get("loc", ())
    return issue(
        "schema_validation_error",
        error.get("msg", "schema validation failed"),
        _scope_for_location(location),
        json_paths=[_json_path(location)],
    )


def _scope_for_location(location: tuple[Any, ...]) -> str:
    if not location:
        return "topology"
    if location[0] == "nodes":
        if len(location) >= 4 and location[2] == "ports":
            return "port"
        return "node"
    if location[0] == "links":
        return "link"
    return "topology"


def _json_path(location: tuple[Any, ...]) -> str:
    if not location:
        return "$"

    parts = ["$"]
    for item in location:
        if isinstance(item, int):
            parts[-1] = f"{parts[-1]}[{item}]"
        else:
            parts.append(f".{item}")
    return "".join(parts)
