from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Link(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    from_port: str
    to_port: str
    from_node: str | None = None
    to_node: str | None = None
