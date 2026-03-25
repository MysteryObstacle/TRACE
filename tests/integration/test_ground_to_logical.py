import shutil
from pathlib import Path

from agent.facade import FakeAgentFacade
from agent.types import AgentResult
from app.stage_runtime import StageRuntime
from app.tplan_runner import TPlanRunner
from app.checkpoint_runner import run_checkpoints
from artifacts.store import ArtifactStore
from stages.registry import STAGE_ORDER, STAGE_SPECS


def test_logical_stage_retries_after_validation_failure() -> None:
    temp_dir = Path('.test_tmp/integration-logical-retry')
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
                            'tgraph_logical': {'profile': 'logical.v1', 'nodes': []},
                            'logical_validator_script': None,
                        },
                    ),
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
                            'tgraph_logical': {'profile': 'logical.v1', 'nodes': [], 'links': []},
                            'logical_validator_script': None,
                        },
                    ),
                ],
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

        result = runner.run('intent')

        assert result.status == 'completed'
        assert result.validation_attempts['logical'] == 2
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_ground_stage_contract_examples_use_explicit_node_sets() -> None:
    prompt_text = Path('prompts/ground.md').read_text(encoding='utf-8')

    assert '"text": "All PLC nodes' not in prompt_text
    assert 'PLC[1..6]' in prompt_text


def test_ground_prompt_declares_four_constraint_families() -> None:
    prompt_text = Path('prompts/ground.md').read_text(encoding='utf-8')

    assert 'graph-level constraints' in prompt_text
    assert 'set-level constraints' in prompt_text
    assert 'relationship-level constraints' in prompt_text
    assert 'physical constraints' in prompt_text
