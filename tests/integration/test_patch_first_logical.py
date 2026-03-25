import shutil
from pathlib import Path

from agent.facade import FakeAgentFacade
from agent.types import AgentResult
from app.checkpoint_runner import run_checkpoints
from app.stage_runtime import StageRuntime
from artifacts.store import ArtifactStore
from stages.registry import STAGE_SPECS


def test_logical_prompt_prefers_semantic_patch_ops_and_link_queries() -> None:
    prompt_text = Path('prompts/logical.md').read_text(encoding='utf-8')

    assert 'connect_nodes' in prompt_text
    assert 'disconnect_nodes' in prompt_text
    assert 'get_link(link_id)' in prompt_text
    assert 'list_links(node_id=None, port_id=None)' in prompt_text


def test_logical_stage_runs_check_author_then_graph_builder() -> None:
    temp_dir = Path('.test_tmp/logical-split-round')
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
                            'logical_checkpoints': [
                                {
                                    'id': 'cp1',
                                    'function_name': 'f1_format',
                                    'input_params': {},
                                    'description': 'format check',
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

        logical_requests = [request for request in facade.requests if request.stage_id == 'logical']
        _, artifact = store.read_latest('logical', 'tgraph_logical') or (None, None)

        assert len(logical_requests) == 2
        assert [node['id'] for node in artifact['nodes']] == ['PLC1']
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
