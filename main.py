from pathlib import Path

import typer

from app.container import build_container
from app.tplan_runner import SessionLayout


app = typer.Typer()


def _resolve_intent_source(intent: str) -> str:
    path = Path(intent)
    if not path.exists():
        return intent
    if path.suffix.lower() != '.md':
        raise typer.BadParameter('Only .md input files are supported when passing an existing file path.')
    return path.read_text(encoding='utf-8')


@app.command()
def run(
    intent: str,
    output_root: Path = typer.Option(Path('runs/default'), '--output-root'),
    session_layout: SessionLayout = typer.Option(SessionLayout.SESSIONED, '--session-layout'),
    debug: bool = typer.Option(False, '--debug/--no-debug'),
    stream: bool = typer.Option(False, '--stream/--no-stream'),
) -> None:
    resolved_intent = _resolve_intent_source(intent)
    container = build_container(
        Path.cwd(),
        run_root=output_root,
        session_layout=session_layout.value,
        debug=debug,
        stream=stream,
    )
    result = container.runner.run(resolved_intent)
    typer.echo(f'completed:{result.run_id}')
    typer.echo(f'artifacts:{result.session_root}')


@app.command()
def resume(
    run_id: str,
    output_root: Path = typer.Option(Path('runs/default'), '--output-root'),
    session_layout: SessionLayout = typer.Option(SessionLayout.SESSIONED, '--session-layout'),
) -> None:
    container = build_container(
        Path.cwd(),
        run_root=output_root,
        session_layout=session_layout.value,
    )
    result = container.runner.resume(run_id)
    typer.echo(f'resumed:{result.run_id}:{result.status}')
    typer.echo(f'artifacts:{result.session_root}')


if __name__ == '__main__':
    app()
