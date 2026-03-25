from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Port(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    ip: str = ""
    cidr: str = ""
