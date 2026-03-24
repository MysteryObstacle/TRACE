import shutil
from pathlib import Path

from agent.facade import FakeAgentFacade
from agent.types import AgentResult
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
                            'tgraph_logical': {'nodes': [{'id': 'PLC1'}, {'id': 'PLC2'}], 'edges': []},
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
                            'tgraph_physical': {'nodes': [{'id': 'PLC1'}, {'id': 'PLC2'}], 'edges': []},
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
