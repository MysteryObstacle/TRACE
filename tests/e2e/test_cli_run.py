from typer.testing import CliRunner

from main import app


def test_run_command_shows_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    assert "run" in result.stdout
