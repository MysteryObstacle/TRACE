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


if __name__ == "__main__":
    app()
