from __future__ import annotations

from typing import Any


def issue(
    code: str,
    message: str,
    *,
    severity: str = "error",
    targets: list[str] | None = None,
    json_paths: list[str] | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "severity": severity,
        "targets": targets or [],
        "json_paths": json_paths or [],
        "provenance": provenance,
    }
