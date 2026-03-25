from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from langsmith import Client
import yaml

from agent.facade import FakeAgentFacade, LangChainAgentFacade
from agent.langchain.engine import LangChainEngine
from agent.langchain.model_factory import build_chat_model
from agent.langchain.tracing import TraceRecorder
from agent.types import AgentResult
from app.checkpoint_runner import run_checkpoints
from app.progress import ConsoleProgressReporter
from app.stage_runtime import StageRuntime
from app.tplan_runner import SessionLayout, TPlanRunner
from app.transition_policy import DEFAULT_STAGE_ORDER
from artifacts.store import ArtifactStore
from stages.registry import STAGE_SPECS


@dataclass
class AppSettings:
    agent_backend: str = 'langchain'
    langsmith_enabled: bool = False
    langsmith_project: str = 'trace-iac'
    langsmith_endpoint: str | None = None
    model_name: str = 'gpt-5-mini'


@dataclass
class AppContainer:
    runner: TPlanRunner
    tracer: TraceRecorder
    settings: AppSettings


def build_container(
    root: str | Path,
    config_dir: str | Path | None = None,
    run_root: str | Path | None = None,
    session_layout: SessionLayout | str = SessionLayout.DIRECT,
    debug: bool = False,
    stream: bool = False,
) -> AppContainer:
    root_path = Path(root)
    _load_dotenv(root_path / '.env')
    config_path = Path(config_dir) if config_dir is not None else root_path / 'configs'
    settings = load_settings(config_path)
    tracer = TraceRecorder(
        enabled=settings.langsmith_enabled,
        project_name=settings.langsmith_project,
        client=build_langsmith_client(settings) if settings.langsmith_enabled else None,
    )
    resolved_run_root = Path(run_root) if run_root is not None else root_path / 'runs' / 'default'
    artifact_store = ArtifactStore(resolved_run_root)
    reporter = ConsoleProgressReporter(enabled=debug, stream_enabled=stream)
    stage_runtime = StageRuntime(
        artifact_store=artifact_store,
        agent_facade=_build_agent_facade(settings, tracer, reporter),
        stage_specs=STAGE_SPECS,
        checkpoint_runner=run_checkpoints,
        tracer=tracer,
        reporter=reporter,
    )
    runner = TPlanRunner(
        stage_runtime=stage_runtime,
        stage_order=DEFAULT_STAGE_ORDER,
        run_root=resolved_run_root,
        tracer=tracer,
        session_layout=session_layout,
        reporter=reporter,
    )
    return AppContainer(runner=runner, tracer=tracer, settings=settings)


def load_settings(config_dir: Path) -> AppSettings:
    app_config = _read_yaml(config_dir / 'app.yaml')
    model_config = _read_yaml(config_dir / 'model.yaml')
    return AppSettings(
        agent_backend=os.environ.get('TRACE_AGENT_BACKEND', app_config.get('agent_backend', 'langchain')),
        langsmith_enabled=_env_bool(
            'TRACE_LANGSMITH_ENABLED',
            _env_bool('LANGSMITH_TRACING', app_config.get('langsmith_enabled', False)),
        ),
        langsmith_project=os.environ.get(
            'TRACE_LANGSMITH_PROJECT',
            os.environ.get('LANGSMITH_PROJECT', app_config.get('langsmith_project', 'trace-iac')),
        ),
        langsmith_endpoint=_env_str(
            'TRACE_LANGSMITH_ENDPOINT',
            os.environ.get(
                'LANGSMITH_ENDPOINT',
                os.environ.get('LANGCHAIN_ENDPOINT', app_config.get('langsmith_endpoint')),
            ),
        ),
        model_name=os.environ.get('TRACE_MODEL_NAME', model_config.get('model_name', 'gpt-5-mini')),
    )


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text())
    return data or {}


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', maxsplit=1)
        os.environ.setdefault(key.strip(), _strip_quotes(value.strip()))


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _env_bool(name: str, default: bool | str | None) -> bool:
    value = os.environ.get(name)
    if value is None:
        if isinstance(default, bool):
            return default
        if default is None:
            return False
        value = str(default)
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _env_str(name: str, default: str | None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        value = default
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def build_langsmith_client(settings: AppSettings) -> Client:
    return Client(
        api_url=settings.langsmith_endpoint,
        api_key=_env_str('TRACE_LANGSMITH_API_KEY', os.environ.get('LANGSMITH_API_KEY')),
    )


def _build_agent_facade(settings: AppSettings, tracer: TraceRecorder, reporter: ConsoleProgressReporter):
    if settings.agent_backend == 'langchain':
        model = build_chat_model(settings.model_name)
        return LangChainAgentFacade(LangChainEngine(model), tracer=tracer, reporter=reporter)
    return FakeAgentFacade(_default_fixtures(), tracer=tracer, reporter=reporter)


def _default_fixtures() -> dict[str, AgentResult]:
    return {
        'ground': AgentResult(
            stage_id='ground',
            output={
                'node_patterns': ['PLC[1..2]', 'HMI1'],
                'logical_constraints': [
                    {
                        'id': 'lc1',
                        'scope': 'topology',
                        'text': 'HMI must reach all PLC nodes.',
                    }
                ],
                'physical_constraints': [
                    {
                        'id': 'pc1',
                        'scope': 'topology',
                        'text': 'Control traffic must stay isolated from management traffic.',
                    }
                ],
            },
        ),
        'logical': AgentResult(
            stage_id='logical',
            output={
                'logical_checkpoints': [
                    {
                        'id': 'cp1',
                        'function_name': 'f1_format',
                        'input_params': {},
                        'description': 'basic format check',
                        'script_ref': None,
                    }
                ],
                'logical_patch_ops': [
                    {'op': 'batch_update_nodes', 'node_ids': ['PLC1', 'PLC2', 'HMI1'], 'changes': {'label': 'initialized'}},
                ],
                'logical_validator_script': None,
            },
        ),
        'physical': AgentResult(
            stage_id='physical',
            output={
                'physical_checkpoints': [
                    {
                        'id': 'cp2',
                        'function_name': 'f1_format',
                        'input_params': {},
                        'description': 'physical format check',
                        'script_ref': None,
                    }
                ],
                'physical_patch_ops': [
                    {'op': 'batch_update_nodes', 'node_ids': ['PLC1', 'PLC2', 'HMI1'], 'changes': {'image': {'id': 'ubuntu-22', 'name': 'Ubuntu 22.04'}, 'flavor': {'vcpu': 2, 'ram': 2048, 'disk': 20}}},
                ],
                'physical_validator_script': None,
            },
        ),
    }
