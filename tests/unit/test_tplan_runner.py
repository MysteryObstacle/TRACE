import shutil
import os
from pathlib import Path

from agent.facade import FakeAgentFacade
from agent.facade import LangChainAgentFacade
from agent.types import AgentResult
from app.container import build_container
from app.stage_runtime import StageRuntime
from app.tplan_runner import SessionLayout, TPlanRunner
from artifacts.store import ArtifactStore
from stages.registry import STAGE_ORDER, STAGE_SPECS


class CaptureReporter:
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def run_started(self, run_id: str, session_root: Path, intent: str) -> None:
        self.events.append(('run_started', run_id, str(session_root), intent))

    def stage_started(self, stage_id: str) -> None:
        self.events.append(('stage_started', stage_id))

    def stage_completed(self, stage_id: str, attempts: int) -> None:
        self.events.append(('stage_completed', stage_id, attempts))

    def repair_round(self, stage_id: str, attempt: int, max_rounds: int) -> None:
        self.events.append(('repair_round', stage_id, attempt, max_rounds))

    def run_completed(self, run_id: str, session_root: Path) -> None:
        self.events.append(('run_completed', run_id, str(session_root)))

    def run_failed(self, run_id: str, session_root: Path, stage_id: str | None, error: str) -> None:
        self.events.append(('run_failed', run_id, str(session_root), stage_id, error))


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
                            'logical_constraints': [
                                {
                                    'id': 'lc1',
                                    'scope': 'topology',
                                    'text': 'The whole logical topology must be connected.',
                                },
                                {
                                    'id': 'lc2',
                                    'scope': 'node_ids',
                                    'text': 'PLC[1..2] must connect to HMI1 through HMI1.',
                                },
                            ],
                            'physical_constraints': [
                                {
                                    'id': 'pc1',
                                    'scope': 'node_ids',
                                    'text': 'PLC[1..2] and HMI1 must use an OpenPLC-compatible image.',
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


def test_runner_passes_runtime_intent_to_ground_stage() -> None:
    temp_dir = Path('.test_tmp/tplan-runner-intent-input-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        facade = FakeAgentFacade(
            {
                'ground': AgentResult(
                    stage_id='ground',
                    output={
                        'node_patterns': ['PLC1'],
                        'logical_constraints': [
                            {
                                'id': 'lc1',
                                'scope': 'topology',
                                'text': 'The whole logical topology must be connected.',
                            }
                        ],
                        'physical_constraints': [
                            {
                                'id': 'pc1',
                                'scope': 'node_ids',
                                'text': 'PLC1 must use image openplc-v3.',
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
        )
        stage_runtime = StageRuntime(
            artifact_store=ArtifactStore(temp_dir),
            agent_facade=facade,
            stage_specs=STAGE_SPECS,
        )
        runner = TPlanRunner(
            stage_runtime=stage_runtime,
            stage_order=STAGE_ORDER,
            run_root=temp_dir,
        )

        runner.run('explicit runtime intent')

        assert facade.requests[0].stage_id == 'ground'
        assert facade.requests[0].inputs['runtime.intent'] == 'explicit runtime intent'
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


def test_container_configures_langsmith_project_and_client(monkeypatch) -> None:
    temp_dir = Path('.test_tmp/container-langsmith-project-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    (temp_dir / 'configs').mkdir(parents=True, exist_ok=True)

    try:
        (temp_dir / 'configs' / 'app.yaml').write_text(
            'langsmith_enabled: true\nlangsmith_project: trace-debug\nagent_backend: fake\n'
        )
        (temp_dir / 'configs' / 'model.yaml').write_text('model_name: gpt-5-mini\n')

        sentinel_client = object()
        monkeypatch.setattr('app.container.build_langsmith_client', lambda settings: sentinel_client)

        container = build_container(temp_dir, config_dir=temp_dir / 'configs')

        assert container.tracer.enabled is True
        assert container.tracer.project_name == 'trace-debug'
        assert container.tracer.client is sentinel_client
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


def test_container_loads_model_settings_from_dotenv(monkeypatch) -> None:
    temp_dir = Path('.test_tmp/container-dotenv-model-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    (temp_dir / 'configs').mkdir(parents=True, exist_ok=True)

    try:
        (temp_dir / 'configs' / 'app.yaml').write_text('langsmith_enabled: false\nagent_backend: langchain\n')
        (temp_dir / 'configs' / 'model.yaml').write_text('model_name: gpt-5-mini\n')
        (temp_dir / '.env').write_text(
            'TRACE_MODEL_NAME=qwen-plus-1220\n'
            'OPENAI_API_KEY=test-key\n'
            'OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1\n'
        )

        monkeypatch.delenv('TRACE_MODEL_NAME', raising=False)
        monkeypatch.delenv('OPENAI_API_KEY', raising=False)
        monkeypatch.delenv('OPENAI_BASE_URL', raising=False)

        seen: dict[str, str | None] = {}

        class DummyModel:
            def invoke(self, messages):
                return {'output': {'node_patterns': ['PLC[1..2]'], 'logical_constraints': [], 'physical_constraints': []}}

        def fake_build_chat_model(model_name: str):
            seen['model_name'] = model_name
            seen['api_key'] = os.environ.get('OPENAI_API_KEY')
            seen['base_url'] = os.environ.get('OPENAI_BASE_URL')
            return DummyModel()

        monkeypatch.setattr('app.container.build_chat_model', fake_build_chat_model)

        container = build_container(temp_dir, config_dir=temp_dir / 'configs')

        assert container.settings.model_name == 'qwen-plus-1220'
        assert seen['model_name'] == 'qwen-plus-1220'
        assert seen['api_key'] == 'test-key'
        assert seen['base_url'] == 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_container_allows_dotenv_to_override_backend(monkeypatch) -> None:
    temp_dir = Path('.test_tmp/container-dotenv-backend-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    (temp_dir / 'configs').mkdir(parents=True, exist_ok=True)

    try:
        (temp_dir / 'configs' / 'app.yaml').write_text('langsmith_enabled: false\nagent_backend: fake\n')
        (temp_dir / 'configs' / 'model.yaml').write_text('model_name: gpt-5-mini\n')
        (temp_dir / '.env').write_text(
            'TRACE_AGENT_BACKEND=langchain\n'
            'TRACE_MODEL_NAME=qwen-plus-1220\n'
            'OPENAI_API_KEY=test-key\n'
        )

        monkeypatch.delenv('TRACE_AGENT_BACKEND', raising=False)
        monkeypatch.delenv('TRACE_MODEL_NAME', raising=False)
        monkeypatch.delenv('OPENAI_API_KEY', raising=False)

        class DummyModel:
            def invoke(self, messages):
                return {'output': {'node_patterns': ['PLC[1..2]'], 'logical_constraints': [], 'physical_constraints': []}}

        monkeypatch.setattr('app.container.build_chat_model', lambda model_name: DummyModel())

        container = build_container(temp_dir, config_dir=temp_dir / 'configs')

        assert container.settings.agent_backend == 'langchain'
        assert container.settings.model_name == 'qwen-plus-1220'
        assert isinstance(container.runner.stage_runtime.agent_facade, LangChainAgentFacade)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_runner_creates_session_subdirectory_when_configured() -> None:
    temp_dir = Path('.test_tmp/tplan-runner-sessioned-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        stage_runtime = StageRuntime(
            artifact_store=ArtifactStore(temp_dir / 'placeholder'),
            agent_facade=FakeAgentFacade(
                {
                    'ground': AgentResult(
                        stage_id='ground',
                        output={
                            'node_patterns': ['PLC1'],
                            'logical_constraints': [
                                {
                                    'id': 'lc1',
                                    'scope': 'topology',
                                    'text': 'The whole logical topology must be connected.',
                                }
                            ],
                            'physical_constraints': [
                                {
                                    'id': 'pc1',
                                    'scope': 'node_ids',
                                    'text': 'PLC1 must use an OpenPLC-compatible image.',
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
        reporter = CaptureReporter()
        runner = TPlanRunner(
            stage_runtime=stage_runtime,
            stage_order=STAGE_ORDER,
            run_root=temp_dir,
            session_layout=SessionLayout.SESSIONED,
            reporter=reporter,
        )

        result = runner.run('user intent')

        session_root = temp_dir / result.run_id
        assert result.session_root == str(session_root)
        assert (session_root / 'run_start.json').exists()
        assert (session_root / 'state.json').exists()
        assert (session_root / 'ground' / 'artifacts').exists()
        assert reporter.events[0][0] == 'run_started'
        assert ('run_completed', result.run_id, str(session_root)) in reporter.events
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_runner_writes_directly_to_run_root_when_configured() -> None:
    temp_dir = Path('.test_tmp/tplan-runner-direct-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        stage_runtime = StageRuntime(
            artifact_store=ArtifactStore(temp_dir / 'placeholder'),
            agent_facade=FakeAgentFacade(
                {
                    'ground': AgentResult(
                        stage_id='ground',
                        output={
                            'node_patterns': ['PLC1'],
                            'logical_constraints': [
                                {
                                    'id': 'lc1',
                                    'scope': 'topology',
                                    'text': 'The whole logical topology must be connected.',
                                }
                            ],
                            'physical_constraints': [
                                {
                                    'id': 'pc1',
                                    'scope': 'node_ids',
                                    'text': 'PLC1 must use an OpenPLC-compatible image.',
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
            session_layout=SessionLayout.DIRECT,
        )

        result = runner.run('user intent')

        assert result.session_root == str(temp_dir)
        assert (temp_dir / 'run_start.json').exists()
        assert (temp_dir / 'state.json').exists()
        assert (temp_dir / 'ground' / 'artifacts').exists()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
