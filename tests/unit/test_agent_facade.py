import shutil
from contextlib import contextmanager
from pathlib import Path

from agent.facade import FakeAgentFacade, LangChainAgentFacade
from agent.types import AgentRequest, AgentResult
from langchain_core.messages import AIMessage, AIMessageChunk


class DummyEngine:
    def __init__(self) -> None:
        self.messages = None
        self.response = {'output': {'node_patterns': ['PLC[1..2]']}}

    def invoke(self, messages):
        self.messages = messages
        return self.response


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


def test_langchain_facade_loads_prompt_file_contents() -> None:
    temp_dir = Path('.test_tmp/agent-facade-prompt-file')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        prompt_path = temp_dir / 'ground.md'
        prompt_path.write_text('real prompt contents', encoding='utf-8')

        engine = DummyEngine()
        facade = LangChainAgentFacade(engine)

        facade.invoke(
            AgentRequest(
                stage_id='ground',
                prompt=str(prompt_path),
                inputs={'intent': 'build something'},
            )
        )

        assert engine.messages is not None
        assert engine.messages[0].content == 'real prompt contents'
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_langchain_facade_formats_runtime_intent_as_separate_human_section() -> None:
    engine = DummyEngine()
    facade = LangChainAgentFacade(engine)

    facade.invoke(
        AgentRequest(
            stage_id='ground',
            prompt='ground prompt',
            inputs={
                'runtime.intent': 'Build a network with R_CORE, PLC1, and FW1.',
                'runtime.mode': 'check_author',
                'ground.expanded_node_ids': ['PLC1'],
            },
        )
    )

    assert engine.messages is not None
    assert len(engine.messages) == 2
    assert 'REAL USER INTENT' in engine.messages[1].content
    assert 'Build a network with R_CORE, PLC1, and FW1.' in engine.messages[1].content
    assert '"ground.expanded_node_ids"' in engine.messages[1].content


def test_langchain_facade_extracts_json_from_fenced_response() -> None:
    engine = DummyEngine()
    engine.response = AIMessage(
        content=(
            '```json\n'
            '{"node_patterns":["PLC[1..2]"],"logical_constraints":[],"physical_constraints":[]}\n'
            '```\n'
            'Explanation: grounded.'
        )
    )
    facade = LangChainAgentFacade(engine)

    result = facade.invoke(
        AgentRequest(
            stage_id='ground',
            prompt='ground prompt',
            inputs={'intent': 'build something'},
        )
    )

    assert result.output['node_patterns'] == ['PLC[1..2]']


def test_langchain_facade_traces_agent_invocation() -> None:
    class CaptureTracer:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        @contextmanager
        def agent_run(self, **kwargs):
            self.calls.append(kwargs)
            yield

    engine = DummyEngine()
    tracer = CaptureTracer()
    facade = LangChainAgentFacade(engine, tracer=tracer)

    facade.invoke(
        AgentRequest(
            stage_id='logical',
            prompt='logical prompt',
            inputs={
                'runtime.mode': 'repair',
                'ground.expanded_node_ids': ['PLC1'],
                'runtime.current_graph': {'profile': 'logical.v1', 'nodes': [], 'links': []},
            },
        )
    )

    assert tracer.calls == [
        {
            'stage_id': 'logical',
            'prompt': 'logical prompt',
            'runtime_mode': 'repair',
            'input_keys': ['ground.expanded_node_ids', 'runtime.current_graph', 'runtime.mode'],
        }
    ]


def test_langchain_facade_streams_tokens_and_still_parses_final_json() -> None:
    class StreamingEngine:
        def __init__(self) -> None:
            self.messages = None

        def invoke(self, messages):
            raise AssertionError('streaming path should not call invoke')

        def stream(self, messages):
            self.messages = messages
            yield AIMessageChunk(content='{"node_patterns":["PLC[1..2]"],')
            yield AIMessageChunk(content='"logical_constraints":[],"physical_constraints":[]}')

    class CaptureReporter:
        def __init__(self) -> None:
            self.events: list[tuple] = []

        def llm_stream_started(self, stage_id: str, runtime_mode: str | None) -> None:
            self.events.append(('started', stage_id, runtime_mode))

        def llm_stream_chunk(self, stage_id: str, text: str) -> None:
            self.events.append(('chunk', stage_id, text))

        def llm_stream_completed(self, stage_id: str) -> None:
            self.events.append(('completed', stage_id))

    engine = StreamingEngine()
    reporter = CaptureReporter()
    facade = LangChainAgentFacade(engine, reporter=reporter)

    result = facade.invoke(
        AgentRequest(
            stage_id='ground',
            prompt='ground prompt',
            inputs={'intent': 'build something'},
        )
    )

    assert result.output['node_patterns'] == ['PLC[1..2]']
    assert reporter.events == [
        ('started', 'ground', None),
        ('chunk', 'ground', '{"node_patterns":["PLC[1..2]"],'),
        ('chunk', 'ground', '"logical_constraints":[],"physical_constraints":[]}'),
        ('completed', 'ground'),
    ]


def test_langchain_facade_respects_disabled_stream_reporter() -> None:
    class StreamingCapableEngine:
        def __init__(self) -> None:
            self.invoke_calls = 0
            self.stream_calls = 0

        def invoke(self, messages):
            self.invoke_calls += 1
            return {'output': {'node_patterns': ['PLC[1..2]'], 'logical_constraints': [], 'physical_constraints': []}}

        def stream(self, messages):
            self.stream_calls += 1
            yield AIMessageChunk(content='{"node_patterns":["PLC[1..2]"]}')

    class DisabledStreamReporter:
        stream_enabled = False

        def llm_stream_started(self, stage_id: str, runtime_mode: str | None) -> None:
            raise AssertionError('streaming should stay disabled')

        def llm_stream_chunk(self, stage_id: str, text: str) -> None:
            raise AssertionError('streaming should stay disabled')

        def llm_stream_completed(self, stage_id: str) -> None:
            raise AssertionError('streaming should stay disabled')

    engine = StreamingCapableEngine()
    facade = LangChainAgentFacade(engine, reporter=DisabledStreamReporter())

    result = facade.invoke(
        AgentRequest(
            stage_id='ground',
            prompt='ground prompt',
            inputs={'intent': 'build something'},
        )
    )

    assert result.output['node_patterns'] == ['PLC[1..2]']
    assert engine.invoke_calls == 1
    assert engine.stream_calls == 0
