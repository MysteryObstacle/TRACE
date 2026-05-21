from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from trace.tools.tgraph.model import LOGICAL_V1, SUPPORTED_PROFILES, TAAL_DEFAULT_V1, TGraphJSON
from trace.tools.tgraph.runtime import TGraphRuntime
from trace.tools.tgraph.validate.issues import issue


def f2_schema(tgraph: dict[str, Any], **_: Any) -> list[dict[str, Any]]:
    profile = tgraph.get("profile")
    if profile not in SUPPORTED_PROFILES:
        return [
            issue(
                "unsupported_profile",
                f"unsupported profile '{profile}'",
                json_paths=["$.profile"],
                provenance={"layer": "f2", "source": "builtin"},
            )
        ]

    try:
        graph = TGraphJSON.model_validate(TGraphRuntime.from_json(tgraph).to_json())
    except ValidationError as exc:
        return [_validation_error_to_issue(item) for item in exc.errors()]

    if profile == LOGICAL_V1:
        return []

    issues: list[dict[str, Any]] = []
    if profile == TAAL_DEFAULT_V1:
        for index, node in enumerate(graph.nodes):
            target = [f"node:{node.id}"]
            if node.type == "computer":
                if node.image is None:
                    issues.append(
                        issue(
                            "computer_image_required",
                            "computer nodes require image metadata",
                            targets=target,
                            json_paths=[f"$.nodes[{index}].image"],
                            provenance={"layer": "f2", "source": "builtin"},
                        )
                    )
                if node.flavor is None:
                    issues.append(
                        issue(
                            "computer_flavor_required",
                            "computer nodes require flavor metadata",
                            targets=target,
                            json_paths=[f"$.nodes[{index}].flavor"],
                            provenance={"layer": "f2", "source": "builtin"},
                        )
                    )
    return issues


def _validation_error_to_issue(error: dict[str, Any]) -> dict[str, Any]:
    location = error.get("loc", ())
    return issue(
        "schema_validation_error",
        error.get("msg", "schema validation failed"),
        json_paths=[_json_path(location)],
        provenance={"layer": "f2", "source": "builtin"},
    )


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
