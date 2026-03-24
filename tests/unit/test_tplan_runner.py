import shutil
from pathlib import Path

from agent.facade import FakeAgentFacade
from agent.facade import LangChainAgentFacade
from agent.types import AgentResult
from app.container import build_container
from app.stage_runtime import StageRuntime
from app.tplan_runner import TPlanRunner
from artifacts.store import ArtifactStore
from stages.registry import STAGE_ORDER, STAGE_SPECS


def test_runner_executes_three_stages_in_order() -> None:
    temp_dir = Path('.test_tmp/tplan-runner-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        stage_runtime = StageRuntime(
            artifact_store=ArtifactStore(temp_dir),
            agent_facade=FakeAgentFacade(
                {
                    'ground': AgentResult(
                        stage_id='ground',
                        output={
                            'node_patterns': ['PLC[1..2]', 'HMI1'],
                            'logical_constraints': [],
                            'physical_constraints': [],
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
                            'tgraph_logical': {'profile': 'logical.v1', 'nodes': [], 'links': []},
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
                            'tgraph_physical': {'profile': 'taal.default.v1', 'nodes': [], 'links': []},
                            'physical_validator_script': None,
                        },
                    ),
                }
            ),
            stage_specs=STAGE_SPECS,
        )
        runner = TPlanRunner(
            stage_runtime=stage_runtime,
            stage_order=STAGE_ORDER,
            run_root=temp_dir,
        )

        result = runner.run('user intent')

        assert result.status == 'completed'
        assert result.stage_history == ['ground', 'logical', 'physical']
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_container_builds_tracing_client_when_enabled() -> None:
    temp_dir = Path('.test_tmp/container-config-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    (temp_dir / 'configs' / 'stages').mkdir(parents=True, exist_ok=True)

    try:
        (temp_dir / 'configs' / 'app.yaml').write_text('langsmith_enabled: true\nagent_backend: fake\n')
        (temp_dir / 'configs' / 'model.yaml').write_text('model_name: gpt-5-mini\n')
        (temp_dir / 'configs' / 'stages' / 'ground.yaml').write_text('id: ground\n')
        (temp_dir / 'configs' / 'stages' / 'logical.yaml').write_text('id: logical\n')
        (temp_dir / 'configs' / 'stages' / 'physical.yaml').write_text('id: physical\n')

        container = build_container(temp_dir, config_dir=temp_dir / 'configs')

        assert container.tracer.enabled is True
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_container_uses_langchain_backend_when_configured(monkeypatch) -> None:
    temp_dir = Path('.test_tmp/container-langchain-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    (temp_dir / 'configs' / 'stages').mkdir(parents=True, exist_ok=True)

    try:
        (temp_dir / 'configs' / 'app.yaml').write_text('langsmith_enabled: false\nagent_backend: langchain\n')
        (temp_dir / 'configs' / 'model.yaml').write_text('model_name: gpt-5-mini\n')
        (temp_dir / 'configs' / 'stages' / 'ground.yaml').write_text('id: ground\n')
        (temp_dir / 'configs' / 'stages' / 'logical.yaml').write_text('id: logical\n')
        (temp_dir / 'configs' / 'stages' / 'physical.yaml').write_text('id: physical\n')

        class DummyModel:
            def invoke(self, messages):
                return {'output': {'node_patterns': ['PLC[1..2]'], 'logical_constraints': [], 'physical_constraints': []}}

        monkeypatch.setattr('app.container.build_chat_model', lambda model_name: DummyModel())

        container = build_container(temp_dir, config_dir=temp_dir / 'configs')

        assert isinstance(container.runner.stage_runtime.agent_facade, LangChainAgentFacade)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_container_defaults_to_langchain_backend(monkeypatch) -> None:
    temp_dir = Path('.test_tmp/container-default-langchain-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    (temp_dir / 'configs').mkdir(parents=True, exist_ok=True)

    try:
        (temp_dir / 'configs' / 'model.yaml').write_text('model_name: gpt-5-mini\n')

        class DummyModel:
            def invoke(self, messages):
                return {'output': {'node_patterns': ['PLC[1..2]'], 'logical_constraints': [], 'physical_constraints': []}}

        monkeypatch.setattr('app.container.build_chat_model', lambda model_name: DummyModel())

        container = build_container(temp_dir, config_dir=temp_dir / 'configs')

        assert container.settings.agent_backend == 'langchain'
        assert isinstance(container.runner.stage_runtime.agent_facade, LangChainAgentFacade)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
