from __future__ import annotations

from pathlib import Path

import typer

from trace.runtime.engine import TraceRuntime


app = typer.Typer(no_args_is_help=True)


@app.callback()
def _callback() -> None:
    """TRACE CLI."""


def build_runtime(output_root: str | Path) -> TraceRuntime:
    return TraceRuntime(output_root=output_root)


def _resolve_intent_source(intent: str) -> str:
    path = Path(intent)
    if not path.exists():
        return intent
    if path.suffix.lower() != ".md":
        raise typer.BadParameter("Only .md input files are supported when passing an existing file path.")
    return path.read_text(encoding="utf-8")


@app.command()
def run(
    intent: str,
    output_root: Path = typer.Option(Path("runs"), "--output-root"),
    run_id: str | None = typer.Option(None, "--run-id"),
) -> None:
    runtime = build_runtime(output_root=output_root)
    result = runtime.run(_resolve_intent_source(intent), run_id=run_id)
    typer.echo(f"completed:{result['run_id']}")
    typer.echo(f"status:{result['status']}")
    if result.get("status") != "completed":
        _echo_run_error(result.get("error"))
        raise typer.Exit(code=1)


@app.command()
def resume(
    run_id: str,
    from_stage: str = typer.Option(..., "--from", "--from-stage"),
    output_root: Path = typer.Option(Path("runs"), "--output-root"),
    new_run_id: str | None = typer.Option(None, "--new-run-id"),
    in_place: bool = typer.Option(False, "--in-place"),
) -> None:
    runtime = build_runtime(output_root=output_root)
    result = runtime.resume(
        run_id,
        from_stage=from_stage,
        new_run_id=new_run_id,
        in_place=in_place,
    )
    typer.echo(f"completed:{result['run_id']}")
    typer.echo(f"status:{result['status']}")
    if result.get("status") != "completed":
        _echo_run_error(result.get("error"))
        raise typer.Exit(code=1)


def _echo_run_error(error: dict | None) -> None:
    if not error:
        return
    stage_id = error.get("stage_id")
    if stage_id:
        typer.echo(f"error_stage:{stage_id}")
    error_type = error.get("type")
    if error_type:
        typer.echo(f"error_type:{error_type}")
    message = error.get("message")
    if message:
        typer.echo(f"error_message:{message}")


if __name__ == "__main__":
    app()
