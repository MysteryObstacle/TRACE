import shutil
from pathlib import Path

from agent.facade import FakeAgentFacade
from agent.types import AgentResult
from app.checkpoint_runner import run_checkpoints
from app.stage_runtime import StageRuntime
from artifacts.store import ArtifactStore
from stages.registry import STAGE_SPECS


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
                                    'op': 'add_node',
                                    'value': {
                                        'id': 'PLC1',
                                        'type': 'computer',
                                        'label': 'PLC1',
                                        'ports': [],
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
