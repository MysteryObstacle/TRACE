from contextlib import contextmanager

from agent.langchain.tracing import TraceRecorder


def test_trace_recorder_uses_langsmith_contexts_when_enabled(monkeypatch) -> None:
    events: list[tuple[str, object]] = []

    @contextmanager
    def fake_tracing_context(**kwargs):
        events.append(('tracing_context', kwargs))
        yield

    @contextmanager
    def fake_trace(name, run_type='chain', **kwargs):
        events.append(('trace', {'name': name, 'run_type': run_type, **kwargs}))
        yield object()

    monkeypatch.setattr('agent.langchain.tracing.tracing_context', fake_tracing_context)
    monkeypatch.setattr('agent.langchain.tracing.trace', fake_trace)
    monkeypatch.setattr('agent.langchain.tracing.get_current_run_tree', lambda: None)

    recorder = TraceRecorder(enabled=True, project_name='trace-test', client='client-token')

    with recorder.root_run(run_id='run123', intent='build network', session_root='runs/default/run123'):
        with recorder.stage_run(stage_id='logical', attempt=2, mode='repair'):
            with recorder.validation_run(stage_id='logical', checkpoint_count=3):
                pass

    tracing_event = next(event for event in events if event[0] == 'tracing_context')
    trace_events = [event[1] for event in events if event[0] == 'trace']

    assert tracing_event[1]['enabled'] is True
    assert tracing_event[1]['project_name'] == 'trace-test'
    assert tracing_event[1]['client'] == 'client-token'
    assert tracing_event[1]['metadata']['run_id'] == 'run123'
    assert any(event['name'] == 'trace.run' for event in trace_events)
    assert any(event['name'] == 'stage.logical' for event in trace_events)
    assert any(event['name'] == 'validation.logical' for event in trace_events)


def test_trace_recorder_is_noop_when_disabled(monkeypatch) -> None:
    called = {'trace': 0, 'context': 0}

    @contextmanager
    def fake_tracing_context(**kwargs):
        called['context'] += 1
        yield

    @contextmanager
    def fake_trace(name, run_type='chain', **kwargs):
        called['trace'] += 1
        yield object()

    monkeypatch.setattr('agent.langchain.tracing.tracing_context', fake_tracing_context)
    monkeypatch.setattr('agent.langchain.tracing.trace', fake_trace)

    recorder = TraceRecorder(enabled=False, project_name='trace-test', client='client-token')

    with recorder.root_run(run_id='run123'):
        with recorder.stage_run(stage_id='ground'):
            pass

    assert called == {'trace': 0, 'context': 0}
