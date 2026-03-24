import shutil
from pathlib import Path

from agent.facade import FakeAgentFacade
from agent.types import AgentResult
from app.stage_runtime import StageRuntime
from artifacts.store import ArtifactStore
from stages.registry import STAGE_SPECS


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
                                    'op': 'add_node',
                                    'value': {
                                        'id': 'PLC1',
                                        'type': 'computer',
                                        'label': 'PLC1',
                                        'ports': [],
                                        'image': None,
                                        'flavor': None,
                                    },
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
