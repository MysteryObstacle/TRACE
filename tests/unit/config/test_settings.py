from trace.config.settings import TraceSettings, load_settings


def test_load_settings_exposes_role_configs(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("TRACE_ROLE_GROUND_AUTHOR_MODEL", "ground-model")
    monkeypatch.setenv("TRACE_ROLE_PHYSICAL_REPAIR_TEMPERATURE", "0.4")

    settings = load_settings(_env_file=None)

    assert isinstance(settings, TraceSettings)
    assert settings.langsmith.enabled is True
    assert settings.roles["ground_author"].model == "ground-model"
    assert settings.roles["physical_repair"].temperature == 0.4
    assert settings.roles["logical_builder"].max_attempts == 3


def test_load_settings_uses_provider_native_settings(monkeypatch):
    monkeypatch.delenv("TRACE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("TRACE_OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("TRACE_LANGSMITH_ENABLED", raising=False)
    monkeypatch.delenv("TRACE_LANGSMITH_ENDPOINT", raising=False)
    monkeypatch.delenv("TRACE_LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("TRACE_LANGSMITH_PROJECT", raising=False)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-langsmith-key")
    monkeypatch.setenv("LANGSMITH_PROJECT", "trace-iac")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    monkeypatch.setenv("TRACE_MODEL_NAME", "qwen-plus-2025-07-28")

    settings = load_settings(_env_file=None)

    assert settings.langsmith.enabled is True
    assert settings.langsmith.endpoint == "https://api.smith.langchain.com"
    assert settings.langsmith.api_key == "test-langsmith-key"
    assert settings.langsmith.project == "trace-iac"
    assert settings.openai_api_key == "test-openai-key"
    assert settings.openai_base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert settings.roles["ground_author"].model == "qwen-plus-2025-07-28"
    assert settings.roles["physical_builder"].model == "qwen-plus-2025-07-28"


def test_load_settings_still_accepts_trace_prefixed_provider_aliases_for_compatibility(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_ENDPOINT", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("TRACE_LANGSMITH_ENABLED", "true")
    monkeypatch.setenv("TRACE_LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
    monkeypatch.setenv("TRACE_LANGSMITH_API_KEY", "test-langsmith-key")
    monkeypatch.setenv("TRACE_LANGSMITH_PROJECT", "trace-iac")
    monkeypatch.setenv("TRACE_OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("TRACE_OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    settings = load_settings(_env_file=None)

    assert settings.langsmith.enabled is True
    assert settings.langsmith.endpoint == "https://api.smith.langchain.com"
    assert settings.langsmith.api_key == "test-langsmith-key"
    assert settings.langsmith.project == "trace-iac"
    assert settings.openai_api_key == "test-openai-key"
    assert settings.openai_base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
