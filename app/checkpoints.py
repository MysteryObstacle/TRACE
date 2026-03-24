from __future__ import annotations

from pathlib import Path
from typing import Any

import orjson


def write_checkpoint(path: str | Path, payload: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))
    return target
