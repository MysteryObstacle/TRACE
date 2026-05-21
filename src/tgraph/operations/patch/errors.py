from __future__ import annotations

from typing import Any

from tgraph.core.errors import TGraphError


class PatchError(TGraphError):
    code = "patch_error"


class PatchSchemaError(PatchError):
    code = "patch_schema_error"


class PatchConflictError(PatchError):
    code = "patch_conflict"


def error_payload(error: TGraphError) -> dict[str, Any]:
    return {"code": error.code, "message": error.message}

