from typer.testing import CliRunner
from pathlib import Path
from types import SimpleNamespace

from main import app


runner = CliRunner()


def test_run_command_shows_help() -> None:
    result = runner.invoke(app, ['run', '--help'])

    assert result.exit_code == 0
    assert 'run' in result.stdout


def test_resume_command_shows_help() -> None:
    result = runner.invoke(app, ['resume', '--help'])

    assert result.exit_code == 0
    assert 'resume' in result.stdout


def test_run_command_accepts_output_and_debug_options(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_build_container(root, **kwargs):
        captured['root'] = root
        captured.update(kwargs)
        return SimpleNamespace(
            runner=SimpleNamespace(
                run=lambda intent: SimpleNamespace(run_id='abc12345', session_root=str(tmp_path / 'out' / 'abc12345'))
            )
        )

    monkeypatch.setattr('main.build_container', fake_build_container)

    result = runner.invoke(
        app,
        [
            'run',
            'demo intent',
            '--output-root',
            str(tmp_path / 'out'),
            '--session-layout',
            'direct',
            '--debug',
            '--stream',
        ],
    )

    assert result.exit_code == 0
    assert captured['run_root'] == tmp_path / 'out'
    assert captured['session_layout'] == 'direct'
    assert captured['debug'] is True
    assert captured['stream'] is True
    assert 'completed:abc12345' in result.stdout


def test_run_command_reads_markdown_file_as_intent(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    intent_file = tmp_path / 'demo.md'
    intent_file.write_text('markdown intent body', encoding='utf-8')

    def fake_run(intent):
        captured['intent'] = intent
        return SimpleNamespace(run_id='abc12345', session_root=str(tmp_path / 'out' / 'abc12345'))

    def fake_build_container(root, **kwargs):
        captured['root'] = root
        captured.update(kwargs)
        return SimpleNamespace(
            runner=SimpleNamespace(run=fake_run)
        )

    monkeypatch.setattr('main.build_container', fake_build_container)

    result = runner.invoke(app, ['run', str(intent_file)])

    assert result.exit_code == 0
    assert captured['intent'] == 'markdown intent body'


def test_run_command_rejects_existing_non_markdown_file(monkeypatch, tmp_path: Path) -> None:
    text_file = tmp_path / 'demo.txt'
    text_file.write_text('plain text body', encoding='utf-8')

    def fake_build_container(root, **kwargs):
        raise AssertionError('build_container should not be called for unsupported file types')

    monkeypatch.setattr('main.build_container', fake_build_container)

    result = runner.invoke(app, ['run', str(text_file)])

    assert result.exit_code != 0
    assert 'Only .md input files are supported' in (result.stdout + result.stderr)
