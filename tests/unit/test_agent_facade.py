from agent.facade import FakeAgentFacade
from agent.types import AgentRequest, AgentResult


def test_fake_agent_facade_returns_fixture_for_stage() -> None:
    facade = FakeAgentFacade(
        {
            'ground': AgentResult(
                stage_id='ground',
                output={
                    'node_patterns': ['PLC[1..2]'],
                    'logical_constraints': [],
                    'physical_constraints': [],
                },
            )
        }
    )

    result = facade.invoke(
        AgentRequest(stage_id='ground', prompt='ground prompt', inputs={})
    )

    assert result.stage_id == 'ground'
    assert result.output['node_patterns'] == ['PLC[1..2]']
