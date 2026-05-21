from __future__ import annotations

from typing import Literal

GraphStage = Literal["logical", "physical"]


def ensure_stage(value: str) -> GraphStage:
    if value not in {"logical", "physical"}:
        raise ValueError(f"unsupported graph stage: {value}")
    return value  # type: ignore[return-value]

