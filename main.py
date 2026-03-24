import typer


app = typer.Typer()


@app.command()
def run() -> None:
    raise typer.Exit()


if __name__ == "__main__":
    app()
