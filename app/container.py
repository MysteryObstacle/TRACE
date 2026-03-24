from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from agent.facade import FakeAgentFacade
from agent.langchain.tracing import TraceRecorder
from agent.types import AgentResult
from app.checkpoint_runner import run_checkpoints
from app.stage_runtime import StageRuntime
from app.tplan_runner import TPlanRunner
from app.transition_policy import DEFAULT_STAGE_ORDER
from artifacts.store import ArtifactStore
from stages.registry import STAGE_SPECS


@dataclass
class AppSettings:
    agent_backend: str = 'fake'
    langsmith_enabled: bool = False
    model_name: str = 'gpt-5-mini'


@dataclass
class AppContainer:
    runner: TPlanRunner
    tracer: TraceRecorder
    settings: AppSettings


def build_container(root: str | Path, config_dir: str | Path | None = None) -> AppContainer:
    root_path = Path(root)
    config_path = Path(config_dir) if config_dir is not None else root_path / 'configs'
    settings = load_settings(config_path)
    tracer = TraceRecorder(enabled=settings.langsmith_enabled)
    run_root = root_path / 'runs' / 'default'
    artifact_store = ArtifactStore(run_root)
    stage_runtime = StageRuntime(
        artifact_store=artifact_store,
        agent_facade=FakeAgentFacade(_default_fixtures()),
        stage_specs=STAGE_SPECS,
        checkpoint_runner=run_checkpoints,
        tracer=tracer,
    )
    runner = TPlanRunner(
        stage_runtime=stage_runtime,
        stage_order=DEFAULT_STAGE_ORDER,
        run_root=run_root,
        tracer=tracer,
    )
    return AppContainer(runner=runner, tracer=tracer, settings=settings)


def load_settings(config_dir: Path) -> AppSettings:
    app_config = _read_yaml(config_dir / 'app.yaml')
    model_config = _read_yaml(config_dir / 'model.yaml')
    return AppSettings(
        agent_backend=app_config.get('agent_backend', 'fake'),
        langsmith_enabled=bool(app_config.get('langsmith_enabled', False)),
        model_name=model_config.get('model_name', 'gpt-5-mini'),
    )


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text())
    return data or {}


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
                        'targets': [],
                        'text': 'HMI must reach all PLC nodes.',
                    }
                ],
                'physical_constraints': [
                    {
                        'id': 'pc1',
                        'scope': 'topology',
                        'targets': [],
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
                'tgraph_logical': {'nodes': [{'id': 'PLC1'}, {'id': 'PLC2'}, {'id': 'HMI1'}], 'edges': []},
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
                'tgraph_physical': {'nodes': [{'id': 'PLC1'}, {'id': 'PLC2'}, {'id': 'HMI1'}], 'edges': []},
                'physical_validator_script': None,
            },
        ),
    }
