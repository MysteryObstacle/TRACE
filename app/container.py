from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent.facade import FakeAgentFacade
from agent.types import AgentResult
from app.stage_runtime import StageRuntime
from app.tplan_runner import TPlanRunner
from app.transition_policy import DEFAULT_STAGE_ORDER
from artifacts.store import ArtifactStore
from stages.registry import STAGE_SPECS


@dataclass
class AppContainer:
    runner: TPlanRunner


def build_container(root: str | Path) -> AppContainer:
    root_path = Path(root)
    run_root = root_path / 'runs' / 'default'
    artifact_store = ArtifactStore(run_root)
    stage_runtime = StageRuntime(
        artifact_store=artifact_store,
        agent_facade=FakeAgentFacade(_default_fixtures()),
        stage_specs=STAGE_SPECS,
    )
    runner = TPlanRunner(
        stage_runtime=stage_runtime,
        stage_order=DEFAULT_STAGE_ORDER,
        run_root=run_root,
    )
    return AppContainer(runner=runner)


def _default_fixtures() -> dict[str, AgentResult]:
    return {
        'ground': AgentResult(
            stage_id='ground',
            output={
                'node_patterns': ['PLC[1..2]', 'HMI1'],
                'logical_constraints': [
                    {
                        'id': 'lc1',
                        'scope': 'topology',
                        'targets': [],
                        'text': 'HMI must reach all PLC nodes.',
                    }
                ],
                'physical_constraints': [
                    {
                        'id': 'pc1',
                        'scope': 'topology',
                        'targets': [],
                        'text': 'Control traffic must stay isolated from management traffic.',
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
                'tgraph_logical': {'nodes': [{'id': 'PLC1'}, {'id': 'PLC2'}, {'id': 'HMI1'}], 'edges': []},
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
                'tgraph_physical': {'nodes': [{'id': 'PLC1'}, {'id': 'PLC2'}, {'id': 'HMI1'}], 'edges': []},
                'physical_validator_script': None,
            },
        ),
    }
