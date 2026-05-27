from typer.testing import CliRunner

from trace.main import app


class DummyRuntime:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, intent, run_id=None):
        self.calls.append((intent, run_id))
        return self.result

    def resume(self, run_id, *, from_stage, new_run_id=None, in_place=False):
        self.calls.append((run_id, from_stage, new_run_id, in_place))
        return self.result


def test_cli_run_accepts_markdown_fixture_and_prints_run_summary(tmp_path, monkeypatch):
    runtime = DummyRuntime(
        {
            "run_id": "run-001",
            "status": "completed",
            "artifacts": {"ground": {}, "logical": {}, "physical": {}},
            "attempt_counters": {"ground": 1, "logical": 1, "physical": 1},
        }
    )

    monkeypatch.setattr("trace.main.build_runtime", lambda output_root: runtime)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "tests/fixtures/intents/sample_intent.md",
            "--output-root",
            str(tmp_path / "runs"),
        ],
    )

    assert result.exit_code == 0
    assert "completed:run-001" in result.stdout
    assert runtime.calls[0][0].startswith("Construct a typical industrial control network")


def test_cli_resume_dispatches_stage_resume(tmp_path, monkeypatch):
    runtime = DummyRuntime(
        {
            "run_id": "run-001-resume-physical",
            "status": "completed",
            "artifacts": {"ground": {}, "logical": {}, "physical": {}},
            "attempt_counters": {"physical": 1},
        }
    )

    monkeypatch.setattr("trace.main.build_runtime", lambda output_root: runtime)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "resume",
            "run-001",
            "--from",
            "physical",
            "--new-run-id",
            "run-001-resume-physical",
            "--output-root",
            str(tmp_path / "runs"),
        ],
    )

    assert result.exit_code == 0
    assert "completed:run-001-resume-physical" in result.stdout
    assert "status:completed" in result.stdout
    assert runtime.calls == [("run-001", "physical", "run-001-resume-physical", False)]
