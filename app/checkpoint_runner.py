from __future__ import annotations

from pathlib import Path
from typing import Any

from app.contracts import ValidationReport
from validators.tgraph_runner import run_tgraph_checks


def run_checkpoints(
    tgraph: dict[str, Any],
    checkpoints: list[dict[str, Any]],
    artifact_root: str | Path,
) -> ValidationReport:
    return run_tgraph_checks(tgraph=tgraph, checkpoints=checkpoints, artifact_root=artifact_root)
