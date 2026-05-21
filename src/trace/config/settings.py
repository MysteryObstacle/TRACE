from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROLE_NAMES = (
    "ground_author",
    "ground_evaluator",
    "logical_author",
    "logical_builder",
    "logical_repair",
    "physical_author",
    "physical_builder",
    "physical_repair",
)


class LangSmithSettings(BaseModel):
    enabled: bool = False
    project: str = "trace-core"
    endpoint: str | None = None
    api_key: str | None = None


class RoleModelSettings(BaseModel):
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_attempts: int = 3


class TraceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRACE_",
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

    model_name: str = "gpt-4o-mini"
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, validation_alias="OPENAI_BASE_URL")

    langsmith_enabled: bool = Field(default=False, validation_alias="LANGSMITH_TRACING")
    langsmith_project: str = Field(default="trace-core", validation_alias="LANGSMITH_PROJECT")
    langsmith_endpoint: str | None = Field(default=None, validation_alias="LANGSMITH_ENDPOINT")
    langsmith_api_key: str | None = Field(default=None, validation_alias="LANGSMITH_API_KEY")

    role_ground_author_model: str | None = None
    role_ground_author_temperature: float = 0.0
    role_ground_author_max_attempts: int = 3

    role_ground_evaluator_model: str | None = None
    role_ground_evaluator_temperature: float = 0.0
    role_ground_evaluator_max_attempts: int = 3

    role_logical_author_model: str | None = None
    role_logical_author_temperature: float = 0.0
    role_logical_author_max_attempts: int = 3

    role_logical_builder_model: str | None = None
    role_logical_builder_temperature: float = 0.0
    role_logical_builder_max_attempts: int = 3

    role_logical_repair_model: str | None = None
    role_logical_repair_temperature: float = 0.1
    role_logical_repair_max_attempts: int = 3

    role_physical_author_model: str | None = None
    role_physical_author_temperature: float = 0.0
    role_physical_author_max_attempts: int = 3

    role_physical_builder_model: str | None = None
    role_physical_builder_temperature: float = 0.0
    role_physical_builder_max_attempts: int = 3

    role_physical_repair_model: str | None = None
    role_physical_repair_temperature: float = 0.1
    role_physical_repair_max_attempts: int = 3

    @property
    def langsmith(self) -> LangSmithSettings:
        return LangSmithSettings(
            enabled=self.langsmith_enabled,
            project=self.langsmith_project,
            endpoint=self.langsmith_endpoint,
            api_key=self.langsmith_api_key,
        )

    @property
    def roles(self) -> dict[str, RoleModelSettings]:
        result: dict[str, RoleModelSettings] = {}
        for role_name in ROLE_NAMES:
            prefix = f"role_{role_name}"
            result[role_name] = RoleModelSettings(
                model=getattr(self, f"{prefix}_model") or self.model_name,
                temperature=getattr(self, f"{prefix}_temperature"),
                max_attempts=getattr(self, f"{prefix}_max_attempts"),
            )
        return result


def load_settings(**overrides: Any) -> TraceSettings:
    return TraceSettings(**overrides)
