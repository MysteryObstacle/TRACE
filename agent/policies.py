from pydantic import BaseModel


class AgentPolicy(BaseModel):
    max_rounds: int = 1
