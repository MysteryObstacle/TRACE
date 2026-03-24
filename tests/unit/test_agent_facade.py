from agent.facade import FakeAgentFacade, LangChainAgentFacade
from agent.types import AgentRequest, AgentResult


class DummyEngine:
    def __init__(self) -> None:
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return {'output': {'node_patterns': ['PLC[1..2]']}}


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


def test_langchain_facade_converts_request_to_messages() -> None:
    engine = DummyEngine()
    facade = LangChainAgentFacade(engine)

    result = facade.invoke(
        AgentRequest(
            stage_id='ground',
            prompt='ground prompt',
            inputs={'ground.expanded_node_ids': ['PLC1']},
        )
    )

    assert result.stage_id == 'ground'
    assert result.output['node_patterns'] == ['PLC[1..2]']
    assert engine.messages is not None
    assert len(engine.messages) >= 1
