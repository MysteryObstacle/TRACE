from __future__ import annotations

from app.contracts import FailureType


class StageRuntimeError(RuntimeError):
    """Raised when stage execution fails."""

    def __init__(self, message: str, *, failure_type: FailureType | None = None) -> None:
        super().__init__(message)
        self.failure_type = failure_type
