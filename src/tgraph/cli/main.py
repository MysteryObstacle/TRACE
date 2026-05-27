from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from tgraph import dump_tgraph, emit_target, inspect_graph, load_tgraph, normalize_graph, validate_graph
from tgraph.operations.validate import ValidationPolicy

app = typer.Typer(help="TGraph IR engine CLI")


@app.command()
def inspect(
    graph_path: Path,
    view: str = typer.Option("summary", "--view"),
    node_id: Optional[str] = typer.Option(None, "--node-id"),
    port_id: Optional[str] = typer.Option(None, "--port-id"),
    source: Optional[str] = typer.Option(None, "--source"),
    target: Optional[str] = typer.Option(None, "--target"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    graph = load_tgraph(graph_path)
    result = inspect_graph(graph, view=view, node_id=node_id, port_id=port_id, source=source, target=target)
    _emit(result, json_output=json_output)


@app.command()
def validate(
    graph_path: Path,
    stage: Optional[str] = typer.Option(None, "--stage"),
    levels: str = typer.Option("f1,f2,f3,f4", "--levels"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    graph = load_tgraph(graph_path)
    policy = ValidationPolicy(levels=[item.strip() for item in levels.split(",") if item.strip()], stage=stage)
    result = validate_graph(graph, policy)
    _emit(result.model_dump(mode="json"), json_output=json_output)


@app.command()
def normalize(
    graph_path: Path,
    out: Optional[Path] = typer.Option(None, "--out"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    graph = normalize_graph(load_tgraph(graph_path, normalize=False))
    payload = dump_tgraph(graph)
    if out is not None:
        out.write_text(dump_tgraph(graph, as_json=True), encoding="utf-8")
    _emit(payload, json_output=json_output)


@app.command("export")
def export_command(
    format_name: str,
    graph_path: Path,
    out: Optional[Path] = typer.Option(None, "--out"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    if format_name != "json":
        _emit({"ok": False, "error": {"code": "export_error", "message": f"unsupported export format: {format_name}"}}, json_output=True)
        return
    graph = load_tgraph(graph_path)
    payload = dump_tgraph(graph)
    if out is not None:
        out.write_text(dump_tgraph(graph, as_json=True), encoding="utf-8")
    _emit(payload, json_output=json_output)


@app.command()
def emit(
    target_name: str,
    graph_path: Path,
    out: Optional[Path] = typer.Option(None, "--out"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    del out
    graph = load_tgraph(graph_path)
    result = emit_target(target_name, graph)
    _emit(result.model_dump(mode="json"), json_output=json_output)


def _emit(payload: dict, *, json_output: bool) -> None:
    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
