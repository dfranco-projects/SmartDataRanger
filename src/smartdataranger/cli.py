"""`ranger` command-line interface. Implemented by Unit 6 (CLI)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from .api import import_dataset
from .errors import SmartDataRangerError
from .models import Diagnostic, FileReport, ImportReport, Severity

app = typer.Typer(help="SmartDataRanger: scan a folder of data files.")

_SEVERITY_STYLES: dict[Severity, str] = {
    Severity.ERROR: "red",
    Severity.WARNING: "yellow",
    Severity.INFO: "dim",
}


def _summary_panel(report: ImportReport) -> Panel:
    counts: Counter[Severity] = Counter(d.severity for d in report.all_diagnostics)
    total_rows = sum(f.metadata.row_count for f in report.files)
    body = (
        f"Root: {escape(str(report.root))}\n"
        f"Files ingested: {len(report.files)}\n"
        f"Total rows: {total_rows}\n"
        f"[red]Errors: {counts[Severity.ERROR]}[/red]  "
        f"[yellow]Warnings: {counts[Severity.WARNING]}[/yellow]  "
        f"[dim]Info: {counts[Severity.INFO]}[/dim]"
    )
    return Panel(body, title="Scan summary", expand=False)


def _profile_table(file_report: FileReport) -> Table:
    table = Table(title=file_report.metadata.file_name)
    table.add_column("Column")
    table.add_column("Dtype")
    table.add_column("Nulls %", justify="right")
    table.add_column("Unique", justify="right")
    table.add_column("Samples")
    for prof in file_report.column_profiles:
        table.add_row(
            prof.name,
            prof.dtype,
            f"{prof.null_pct:.1f}",
            str(prof.unique_count),
            ", ".join(prof.sample_values),
        )
    return table


def _diagnostic_line(diag: Diagnostic) -> str:
    style = _SEVERITY_STYLES[diag.severity]
    location = escape(diag.file) if diag.file else "<dataset>"
    if diag.column:
        location += f":{escape(diag.column)}"
    return (
        f"[{style}]{diag.severity.name}[/{style}] "
        f"{escape(diag.code)} {location} — {escape(diag.message)}"
    )


def _render_report(console: Console, report: ImportReport) -> None:
    console.print(_summary_panel(report))
    for file_report in report.files:
        if file_report.column_profiles:
            console.print(_profile_table(file_report))
    diagnostics = report.all_diagnostics
    if diagnostics:
        console.print("[bold]Diagnostics[/bold]")
        for diag in diagnostics:
            console.print(_diagnostic_line(diag))
    else:
        console.print("[green]No issues found.[/green]")


@app.callback()
def callback() -> None:
    """SmartDataRanger: scan a folder of data files."""


@app.command()
def scan(
    path: Path,
    profile: bool = typer.Option(True, help="Compute per-column profiles."),
    json_output: bool = typer.Option(False, "--json", help="Emit the report as JSON."),
    write_metadata: bool = typer.Option(True, help="Write reproducible metadata.json."),
) -> None:
    """Run import_dataset and render a rich report (or JSON).

    Exits 1 if the report contains error-severity diagnostics.
    """
    try:
        _, report = import_dataset(path, profile=profile, write_metadata=write_metadata)
    except SmartDataRangerError as exc:
        Console(stderr=True).print(f"[red]error:[/red] {escape(str(exc))}")
        raise typer.Exit(code=2) from exc

    if json_output:
        typer.echo(json.dumps(report.to_dict(), indent=2))
    else:
        _render_report(Console(), report)

    if report.has_errors():
        raise typer.Exit(code=1)


def main() -> None:
    app()
