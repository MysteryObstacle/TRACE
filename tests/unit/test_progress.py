from app.progress import ConsoleProgressReporter


def test_console_progress_reporter_streams_llm_output_when_enabled() -> None:
    lines: list[str] = []
    chunks: list[str] = []
    reporter = ConsoleProgressReporter(
        enabled=False,
        stream_enabled=True,
        printer=lines.append,
        stream_writer=chunks.append,
    )

    reporter.llm_stream_started('logical', 'repair')
    reporter.llm_stream_chunk('logical', '{"logical_patch_ops":')
    reporter.llm_stream_chunk('logical', '[]}')
    reporter.llm_stream_completed('logical')

    assert lines == ['llm:logical:start mode=repair', 'llm:logical:end']
    assert chunks == ['{"logical_patch_ops":', '[]}', '\n']


def test_console_progress_reporter_suppresses_llm_stream_when_disabled() -> None:
    lines: list[str] = []
    chunks: list[str] = []
    reporter = ConsoleProgressReporter(
        enabled=False,
        stream_enabled=False,
        printer=lines.append,
        stream_writer=chunks.append,
    )

    reporter.llm_stream_started('ground', None)
    reporter.llm_stream_chunk('ground', '{"node_patterns":[]}')
    reporter.llm_stream_completed('ground')

    assert lines == []
    assert chunks == []
