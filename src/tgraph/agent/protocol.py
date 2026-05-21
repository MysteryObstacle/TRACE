from __future__ import annotations

from pathlib import Path


def schema_paths() -> dict[str, Path]:
    root = Path(__file__).resolve().parent / "schemas"
    return {
        "tgraph": root / "tgraph.schema.json",
        "patch": root / "patch.schema.json",
        "validation_report": root / "validation-report.schema.json",
        "inspect_result": root / "inspect-result.schema.json",
    }

