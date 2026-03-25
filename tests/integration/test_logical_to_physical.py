import shutil
from pathlib import Path

from agent.facade import FakeAgentFacade
from agent.types import AgentResult
from app.stage_runtime import StageRuntime
from app.tplan_runner import TPlanRunner
from app.checkpoint_runner import run_checkpoints
from artifacts.store import ArtifactStore
from stages.registry import STAGE_ORDER, STAGE_SPECS


def test_physical_stage_reads_ground_and_logical_outputs() -> None:
    temp_dir = Path('.test_tmp/integration-physical-inputs')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        facade = FakeAgentFacade(
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
                                'description': 'format check',
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
                                'description': 'format check',
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
            checkpoint_runner=run_checkpoints,
        )
        runner = TPlanRunner(stage_runtime=stage_runtime, stage_order=STAGE_ORDER, run_root=temp_dir)

        runner.run('intent')

        physical_request = next(request for request in facade.requests if request.stage_id == 'physical')
        assert 'ground.expanded_node_ids' in physical_request.inputs
        assert 'logical.logical_checkpoints' in physical_request.inputs
        assert 'logical.tgraph_logical' in physical_request.inputs
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
