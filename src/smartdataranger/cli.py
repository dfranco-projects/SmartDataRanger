"""`ranger` command-line interface. Implemented by Unit 6 (CLI)."""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(help="SmartDataRanger: scan a folder of data files.")


@app.command()
def scan(
    path: Path,
    profile: bool = typer.Option(True, help="Compute per-column profiles."),
    json_output: bool = typer.Option(False, "--json", help="Emit the report as JSON."),
    write_metadata: bool = typer.Option(True, help="Write reproducible metadata.json."),
) -> None:
    """Run import_dataset and render a rich report (or JSON). Exit 1 if the report
    contains error-severity diagnostics."""
    raise NotImplementedError


def main() -> None:
    app()
