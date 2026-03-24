import shutil
from pathlib import Path

from agent.facade import FakeAgentFacade
from agent.types import AgentResult
from app.stage_runtime import StageRuntime
from artifacts.store import ArtifactStore
from stages.registry import STAGE_SPECS


def test_stage_runtime_passes_declared_artifacts_to_agent() -> None:
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
                            'tgraph_logical': {'nodes': [{'id': 'PLC1'}], 'edges': []},
                            'logical_validator_script': None,
                        },
                    )
                }
            ),
            stage_specs=STAGE_SPECS,
        )

        result = runtime.run_stage('logical')

        assert result.stage_id == 'logical'
        assert 'ground.expanded_node_ids' in result.inputs
        assert 'ground.logical_constraints' in result.inputs
        assert store.read_latest('logical', 'logical_checkpoints') is not None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
