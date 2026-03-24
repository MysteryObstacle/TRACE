from pathlib import Path

import typer

from app.container import build_container


app = typer.Typer()


@app.command()
def run(intent: str) -> None:
    container = build_container(Path.cwd())
    result = container.runner.run(intent)
    typer.echo(f'completed:{result.run_id}')


@app.command()
def resume(run_id: str) -> None:
    container = build_container(Path.cwd())
    result = container.runner.resume(run_id)
    typer.echo(f'resumed:{result.run_id}:{result.status}')


if __name__ == '__main__':
    app()
