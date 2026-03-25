import shutil
from contextlib import contextmanager
from pathlib import Path

from agent.facade import FakeAgentFacade
from agent.types import AgentResult
from app.checkpoint_runner import run_checkpoints
from app.errors import StageRuntimeError
from app.stage_runtime import StageRuntime
from artifacts.store import ArtifactStore
from stages.registry import STAGE_SPECS


class CaptureReporter:
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def repair_round(self, stage_id: str, attempt: int, max_rounds: int) -> None:
        self.events.append(('repair_round', stage_id, attempt, max_rounds))


def test_stage_runtime_persists_logical_profile_payload() -> None:
    temp_dir = Path('.test_tmp/stage-runtime-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        store = ArtifactStore(temp_dir)
        store.write(stage='ground', name='expanded_node_ids', data=['PLC1', 'PLC2'])
        store.write(
            stage='ground',
            name='logical_constraints',
            data=[
                {
                    'id': 'lc1',
                    'scope': 'topology',
                    'targets': [],
                    'text': 'HMI must reach every PLC.',
                }
            ],
        )

        runtime = StageRuntime(
            artifact_store=store,
            agent_facade=FakeAgentFacade(
                {
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
                    )
                }
            ),
            stage_specs=STAGE_SPECS,
        )

        result = runtime.run_stage('logical')
        artifact_ref, artifact = store.read_latest('logical', 'tgraph_logical') or (None, None)

        assert result.stage_id == 'logical'
        assert artifact_ref is not None
        assert artifact['profile'] == 'logical.v1'
        assert 'links' in artifact
        assert 'edges' not in artifact
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_stage_runtime_accepts_logical_patch_round_output() -> None:
    temp_dir = Path('.test_tmp/stage-runtime-patch-output')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        store = ArtifactStore(temp_dir)
        store.write(stage='ground', name='expanded_node_ids', data=['PLC1'])
        store.write(
            stage='ground',
            name='logical_constraints',
            data=[{'id': 'lc1', 'scope': 'node_ids', 'text': 'PLC1 must exist.'}],
        )

        runtime = StageRuntime(
            artifact_store=store,
            agent_facade=FakeAgentFacade(
                {
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
                                {
                                    'op': 'batch_update_nodes',
                                    'node_ids': ['PLC1'],
                                    'changes': {'label': 'PLC1'},
                                }
                            ],
                            'logical_validator_script': None,
                        },
                    )
                }
            ),
            stage_specs=STAGE_SPECS,
        )

        result = runtime.run_stage('logical')
        artifact_ref, artifact = store.read_latest('logical', 'tgraph_logical') or (None, None)

        assert result.stage_id == 'logical'
        assert artifact_ref is not None
        assert [node['id'] for node in artifact['nodes']] == ['PLC1']
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_logical_repair_round_receives_latest_graph_and_report() -> None:
    temp_dir = Path('.test_tmp/stage-runtime-logical-repair')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        store = ArtifactStore(temp_dir)
        store.write(stage='ground', name='expanded_node_ids', data=['PLC1'])
        store.write(
            stage='ground',
            name='logical_constraints',
            data=[{'id': 'lc1', 'scope': 'node_ids', 'text': 'PLC1 must exist.'}],
        )

        facade = FakeAgentFacade(
            {
                'logical': [
                    AgentResult(
                        stage_id='logical',
                        output={
                            'logical_checkpoints': [
                                {
                                    'id': 'cp1',
                                    'function_name': 'required_type_check',
                                    'input_params': {'node_id': 'PLC1', 'required_type': 'switch'},
                                    'description': 'requires plc node type',
                                    'script_ref': 'logical_validator.py',
                                }
                            ],
                            'logical_validator_script': (
                                'def required_type_check(tgraph, **kwargs):\n'
                                '    node_id = kwargs.get("node_id")\n'
                                '    required_type = kwargs.get("required_type")\n'
                                '    for index, node in enumerate(tgraph.get("nodes", [])):\n'
                                '        if node.get("id") == node_id and node.get("type") != required_type:\n'
                                '            return [{"code": "wrong_node_type", "message": "node type mismatch", "severity": "error", "scope": "node", "targets": [node_id], "json_paths": [f"$.nodes[{index}].type"]}]\n'
                                '    return []\n'
                            ),
                        },
                    ),
                    AgentResult(
                        stage_id='logical',
                        output={
                            'logical_checkpoints': [
                                {
                                    'id': 'cp1',
                                    'function_name': 'required_type_check',
                                    'input_params': {'node_id': 'PLC1', 'required_type': 'switch'},
                                    'description': 'requires plc node type',
                                    'script_ref': 'logical_validator.py',
                                }
                            ],
                            'logical_patch_ops': [],
                            'logical_validator_script': (
                                'def required_type_check(tgraph, **kwargs):\n'
                                '    node_id = kwargs.get("node_id")\n'
                                '    required_type = kwargs.get("required_type")\n'
                                '    for index, node in enumerate(tgraph.get("nodes", [])):\n'
                                '        if node.get("id") == node_id and node.get("type") != required_type:\n'
                                '            return [{"code": "wrong_node_type", "message": "node type mismatch", "severity": "error", "scope": "node", "targets": [node_id], "json_paths": [f"$.nodes[{index}].type"]}]\n'
                                '    return []\n'
                            ),
                        },
                    ),
                    AgentResult(
                        stage_id='logical',
                        output={
                            'logical_patch_ops': [
                                {
                                    'op': 'batch_update_nodes',
                                    'node_ids': ['PLC1'],
                                    'changes': {'type': 'switch'},
                                }
                            ],
                        },
                    ),
                ]
            }
        )

        runtime = StageRuntime(
            artifact_store=store,
            agent_facade=facade,
            stage_specs=STAGE_SPECS,
            checkpoint_runner=run_checkpoints,
        )

        runtime.run_stage('logical')

        repair_request = facade.requests[-1]
        assert repair_request.inputs['runtime.mode'] == 'repair'
        assert repair_request.inputs['runtime.validation_report']['ok'] is False
        assert repair_request.inputs['runtime.current_graph']['profile'] == 'logical.v1'
        assert repair_request.inputs['runtime.repair_context']['open_issues'] == ['wrong_node_type: node type mismatch']
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_logical_repair_round_handles_patch_application_failure() -> None:
    temp_dir = Path('.test_tmp/stage-runtime-logical-patch-repair')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        store = ArtifactStore(temp_dir)
        store.write(stage='ground', name='expanded_node_ids', data=['PLC1'])
        store.write(
            stage='ground',
            name='logical_constraints',
            data=[{'id': 'lc1', 'scope': 'node_ids', 'text': 'PLC1 must exist.'}],
        )

        facade = FakeAgentFacade(
            {
                'logical': [
                    AgentResult(
                        stage_id='logical',
                        output={
                            'logical_checkpoints': [
                                {
                                    'id': 'cp1',
                                    'function_name': 'f1_format',
                                    'input_params': {},
                                    'description': 'format check',
                                    'script_ref': None,
                                }
                            ],
                            'logical_validator_script': None,
                        },
                    ),
                    AgentResult(
                        stage_id='logical',
                        output={
                            'logical_patch_ops': [
                                {
                                    'op': 'add_link',
                                    'value': {
                                        'id': 'PLC1:p1--PLC1:p2',
                                        'from_port': 'PLC1:p1',
                                        'to_port': 'PLC1:p2',
                                        'from_node': 'PLC1',
                                        'to_node': 'PLC1',
                                    },
                                }
                            ],
                        },
                    ),
                    AgentResult(
                        stage_id='logical',
                        output={
                            'logical_patch_ops': [],
                        },
                    ),
                ]
            }
        )

        runtime = StageRuntime(
            artifact_store=store,
            agent_facade=facade,
            stage_specs=STAGE_SPECS,
        )

        result = runtime.run_stage('logical')

        repair_request = facade.requests[-1]
        assert result.attempts == 2
        assert repair_request.inputs['runtime.mode'] == 'repair'
        assert repair_request.inputs['runtime.validation_report']['issues'][0]['code'] == 'patch_link_endpoint_not_found'
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_physical_stage_boundary_error_does_not_mutate_logical_links() -> None:
    temp_dir = Path('.test_tmp/stage-runtime-physical-boundary')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        store = ArtifactStore(temp_dir)
        store.write(stage='ground', name='expanded_node_ids', data=['PLC1', 'SW1'])
        store.write(stage='ground', name='physical_constraints', data=[{'id': 'pc1', 'scope': 'topology', 'text': 'Preserve logical connectivity.'}])
        store.write(
            stage='logical',
            name='logical_checkpoints',
            data=[
                {
                    'id': 'cp1',
                    'function_name': 'f1_format',
                    'input_params': {},
                    'description': 'format check',
                    'script_ref': None,
                }
            ],
        )
        store.write(
            stage='logical',
            name='tgraph_logical',
            data={
                'profile': 'logical.v1',
                'nodes': [
                    {'id': 'PLC1', 'type': 'computer', 'label': 'PLC1', 'ports': [{'id': 'PLC1:p1', 'ip': '', 'cidr': ''}], 'image': None, 'flavor': None},
                    {'id': 'SW1', 'type': 'switch', 'label': 'SW1', 'ports': [{'id': 'SW1:p1', 'ip': '', 'cidr': '10.0.0.0/24'}], 'image': None, 'flavor': None},
                ],
                'links': [
                    {
                        'id': 'PLC1:p1--SW1:p1',
                        'from_port': 'PLC1:p1',
                        'to_port': 'SW1:p1',
                        'from_node': 'PLC1',
                        'to_node': 'SW1',
                    }
                ],
            },
        )

        runtime = StageRuntime(
            artifact_store=store,
            agent_facade=FakeAgentFacade(
                {
                    'physical': [
                        AgentResult(
                            stage_id='physical',
                            output={
                                'physical_checkpoints': [
                                    {
                                        'id': 'cp2',
                                        'function_name': 'f1_format',
                                        'input_params': {},
                                        'description': 'format check',
                                        'script_ref': None,
                                    }
                                ],
                            },
                        ),
                        AgentResult(
                            stage_id='physical',
                            output={
                                'physical_patch_ops': [
                                    {
                                        'op': 'add_link',
                                        'value': {
                                            'id': 'PLC1:p1--PLC1:p1',
                                            'from_port': 'PLC1:p1',
                                            'to_port': 'PLC1:p1',
                                            'from_node': 'PLC1',
                                            'to_node': 'PLC1',
                                        },
                                    }
                                ],
                            },
                        ),
                    ]
                }
            ),
            stage_specs=STAGE_SPECS,
        )

        try:
            runtime.run_stage('physical')
        except StageRuntimeError as exc:
            assert 'stage boundary' in str(exc).lower()
        else:
            raise AssertionError('Expected StageRuntimeError for physical stage boundary violation.')
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_physical_validation_resolves_logical_checkpoint_scripts_from_logical_artifacts() -> None:
    temp_dir = Path('.test_tmp/stage-runtime-physical-logical-script')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        store = ArtifactStore(temp_dir)
        logical_checkpoints = [
            {
                'id': 'cp1',
                'function_name': 'check_plc_exists',
                'input_params': {'node_id': 'PLC1'},
                'description': 'logical custom check',
                'script_ref': 'logical_validator.py',
            }
        ]
        logical_graph = {
            'profile': 'logical.v1',
            'nodes': [
                {'id': 'PLC1', 'type': 'computer', 'label': 'PLC1', 'ports': [], 'image': None, 'flavor': None},
            ],
            'links': [],
        }
        physical_graph = {
            'profile': 'taal.default.v1',
            'nodes': [
                {'id': 'PLC1', 'type': 'computer', 'label': 'PLC1', 'ports': [], 'image': None, 'flavor': None},
            ],
            'links': [],
        }
        store.write(stage='logical', name='logical_checkpoints', data=logical_checkpoints)
        store.write(stage='logical', name='tgraph_logical', data=logical_graph)

        runtime = StageRuntime(
            artifact_store=store,
            agent_facade=FakeAgentFacade({}),
            stage_specs=STAGE_SPECS,
            checkpoint_runner=run_checkpoints,
        )
        runtime._materialize_validator_script(
            'logical',
            logical_checkpoints,
            (
                'def check_plc_exists(tgraph, **kwargs):\n'
                '    node_id = kwargs["node_id"]\n'
                '    if tgraph.get_node(node_id) is None:\n'
                '        return [{"code": "missing_node", "message": "missing node", "severity": "error", "scope": "node", "targets": [node_id], "json_paths": []}]\n'
                '    return []\n'
            ),
        )

        report = runtime._validate_physical_output(
            {
                'physical_checkpoints': [
                    {
                        'id': 'pc1',
                        'function_name': 'f1_format',
                        'input_params': {},
                        'description': 'format check',
                        'script_ref': None,
                    }
                ],
                'physical_validator_script': None,
            },
            physical_graph,
        )

        assert report is not None
        assert report.ok is True
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_logical_stage_reports_repair_round_events() -> None:
    temp_dir = Path('.test_tmp/stage-runtime-repair-events')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        store = ArtifactStore(temp_dir)
        store.write(stage='ground', name='expanded_node_ids', data=['PLC1'])
        store.write(
            stage='ground',
            name='logical_constraints',
            data=[{'id': 'lc1', 'scope': 'node_ids', 'text': 'PLC1 must be a switch.'}],
        )

        facade = FakeAgentFacade(
            {
                'logical': [
                    AgentResult(
                        stage_id='logical',
                        output={
                            'logical_checkpoints': [
                                {
                                    'id': 'cp1',
                                    'function_name': 'required_type_check',
                                    'input_params': {'node_id': 'PLC1', 'required_type': 'switch'},
                                    'description': 'requires switch node type',
                                    'script_ref': 'logical_validator.py',
                                }
                            ],
                            'logical_validator_script': (
                                'def required_type_check(tgraph, **kwargs):\n'
                                '    node_id = kwargs.get("node_id")\n'
                                '    required_type = kwargs.get("required_type")\n'
                                '    for node in tgraph.get("nodes", []):\n'
                                '        if node.get("id") == node_id and node.get("type") != required_type:\n'
                                '            return [{"code": "wrong_node_type", "message": "node type mismatch", "severity": "error", "scope": "node", "targets": [node_id], "json_paths": []}]\n'
                                '    return []\n'
                            ),
                        },
                    ),
                    AgentResult(
                        stage_id='logical',
                        output={
                            'logical_patch_ops': [],
                        },
                    ),
                    AgentResult(
                        stage_id='logical',
                        output={
                            'logical_patch_ops': [
                                {
                                    'op': 'batch_update_nodes',
                                    'node_ids': ['PLC1'],
                                    'changes': {'type': 'switch'},
                                }
                            ],
                        },
                    ),
                ]
            }
        )
        reporter = CaptureReporter()
        runtime = StageRuntime(
            artifact_store=store,
            agent_facade=facade,
            stage_specs=STAGE_SPECS,
            checkpoint_runner=run_checkpoints,
            reporter=reporter,
        )

        runtime.run_stage('logical')

        assert ('repair_round', 'logical', 2, STAGE_SPECS['logical'].max_rounds) in reporter.events
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_stage_runtime_traces_patch_and_validation_runs() -> None:
    class CaptureTracer:
        def __init__(self) -> None:
            self.events: list[tuple[str, dict]] = []

        @contextmanager
        def stage_run(self, **kwargs):
            self.events.append(('stage_run', kwargs))
            yield

        @contextmanager
        def patch_run(self, **kwargs):
            self.events.append(('patch_run', kwargs))
            yield

        @contextmanager
        def validation_run(self, **kwargs):
            self.events.append(('validation_run', kwargs))
            yield

    temp_dir = Path('.test_tmp/stage-runtime-tracing-events')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        store = ArtifactStore(temp_dir)
        store.write(stage='ground', name='expanded_node_ids', data=['PLC1'])
        store.write(
            stage='ground',
            name='logical_constraints',
            data=[{'id': 'lc1', 'scope': 'node_ids', 'text': 'PLC1 must exist.'}],
        )

        tracer = CaptureTracer()
        runtime = StageRuntime(
            artifact_store=store,
            agent_facade=FakeAgentFacade(
                {
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
                                {
                                    'op': 'batch_update_nodes',
                                    'node_ids': ['PLC1'],
                                    'changes': {'label': 'PLC1'},
                                }
                            ],
                            'logical_validator_script': None,
                        },
                    )
                }
            ),
            stage_specs=STAGE_SPECS,
            checkpoint_runner=run_checkpoints,
            tracer=tracer,
        )

        runtime.run_stage('logical')

        assert ('stage_run', {'stage_id': 'logical'}) in tracer.events
        assert any(event[0] == 'patch_run' and event[1]['stage_id'] == 'logical' for event in tracer.events)
        assert any(event[0] == 'validation_run' and event[1]['stage_id'] == 'logical' for event in tracer.events)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
