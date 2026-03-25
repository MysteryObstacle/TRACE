import shutil
from pathlib import Path

from agent.facade import FakeAgentFacade
from agent.types import AgentResult
from app.checkpoint_runner import run_checkpoints
from app.errors import StageRuntimeError
from app.stage_runtime import StageRuntime
from artifacts.store import ArtifactStore
from stages.registry import STAGE_SPECS


def test_physical_prompt_mentions_semantic_patch_surface_and_link_queries() -> None:
    prompt_text = Path('prompts/physical.md').read_text(encoding='utf-8')

    assert 'batch_update_nodes' in prompt_text
    assert 'connect_nodes' in prompt_text
    assert 'disconnect_nodes' in prompt_text
    assert 'get_link(link_id)' in prompt_text
    assert 'list_links(node_id=None, port_id=None)' in prompt_text


def test_physical_stage_runs_check_author_then_graph_builder() -> None:
    temp_dir = Path('.test_tmp/physical-split-round')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        store = ArtifactStore(temp_dir)
        store.write(stage='ground', name='expanded_node_ids', data=['PLC1'])
        store.write(stage='ground', name='physical_constraints', data=[{'id': 'pc1', 'scope': 'node_ids', 'text': 'PLC1 must have an image.'}])
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
                'nodes': [{'id': 'PLC1', 'type': 'computer', 'label': 'PLC1', 'ports': [], 'image': None, 'flavor': None}],
                'links': [],
            },
        )

        facade = FakeAgentFacade(
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
                            'physical_validator_script': None,
                        },
                    ),
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
                            'physical_patch_ops': [
                                {
                                    'op': 'batch_update_nodes',
                                    'node_ids': ['PLC1'],
                                    'changes': {
                                        'image': {'id': 'ubuntu-22', 'name': 'Ubuntu 22.04'},
                                        'flavor': {'vcpu': 2, 'ram': 2048, 'disk': 20},
                                    },
                                }
                            ],
                            'physical_validator_script': None,
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

        runtime.run_stage('physical')

        physical_requests = [request for request in facade.requests if request.stage_id == 'physical']
        _, artifact = store.read_latest('physical', 'tgraph_physical') or (None, None)

        assert len(physical_requests) == 2
        assert [node['id'] for node in artifact['nodes']] == ['PLC1']
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_physical_validation_runs_logical_and_physical_checkpoints_together() -> None:
    temp_dir = Path('.test_tmp/physical-combined-checkpoints')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        store = ArtifactStore(temp_dir)
        store.write(stage='ground', name='expanded_node_ids', data=['PLC1'])
        store.write(stage='ground', name='physical_constraints', data=[{'id': 'pc1', 'scope': 'node_ids', 'text': 'PLC1 must keep physical metadata.'}])
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
                'nodes': [{'id': 'PLC1', 'type': 'computer', 'label': 'PLC1', 'ports': [], 'image': None, 'flavor': None}],
                'links': [],
            },
        )

        facade = FakeAgentFacade(
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
                                    'op': 'batch_update_nodes',
                                    'node_ids': ['PLC1'],
                                    'changes': {
                                        'image': {'id': 'ubuntu-22', 'name': 'Ubuntu 22.04'},
                                        'flavor': {'vcpu': 2, 'ram': 2048, 'disk': 20},
                                    },
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

        result = runtime.run_stage('physical')
        physical_request = [request for request in facade.requests if request.stage_id == 'physical'][-1]

        assert result.validation_report is not None
        assert result.validation_report.ok is True
        assert 'logical.logical_checkpoints' in physical_request.inputs
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_physical_stage_boundary_error_does_not_mutate_logical_links_integration() -> None:
    temp_dir = Path('.test_tmp/physical-stage-boundary')
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

        facade = FakeAgentFacade(
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
        )

        runtime = StageRuntime(
            artifact_store=store,
            agent_facade=facade,
            stage_specs=STAGE_SPECS,
            checkpoint_runner=run_checkpoints,
        )

        try:
            runtime.run_stage('physical')
        except StageRuntimeError as exc:
            assert 'stage boundary' in str(exc).lower()
        else:
            raise AssertionError('Expected stage boundary error.')
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
