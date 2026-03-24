from typer.testing import CliRunner

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
