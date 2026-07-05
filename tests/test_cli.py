"""Tests for the `ranger` CLI (Unit 6)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from typer.testing import CliRunner

from smartdataranger import cli
from smartdataranger.errors import SmartDataRangerError
from smartdataranger.models import (
    ColumnProfile,
    Diagnostic,
    FileMetadata,
    FileReport,
    ImportReport,
    Severity,
)

runner = CliRunner()


def make_report(
    root: Path, diagnostics: list[Diagnostic] | None = None, with_profiles: bool = True
) -> ImportReport:
    metadata = FileMetadata(
        file_name="sales.csv",
        file_type=".csv",
        reader="csv",
        reader_kwargs={},
        columns=["id", "name"],
        row_count=4,
        source="sales.csv",
    )
    profiles = (
        [
            ColumnProfile(
                name="id",
                dtype="int64",
                non_null_count=4,
                null_count=0,
                null_pct=0.0,
                unique_count=3,
                cardinality_pct=75.0,
                sample_values=["1", "2", "3"],
            ),
            ColumnProfile(
                name="name",
                dtype="object",
                non_null_count=3,
                null_count=1,
                null_pct=25.0,
                unique_count=3,
                cardinality_pct=100.0,
                sample_values=["ada", "grace", "alan"],
            ),
        ]
        if with_profiles
        else []
    )
    file_report = FileReport(
        metadata=metadata,
        diagnostics=diagnostics or [],
        column_profiles=profiles,
        duplicate_row_count=1,
    )
    return ImportReport(root=root, files=[file_report])


def patch_import(monkeypatch: pytest.MonkeyPatch, report: ImportReport) -> dict[str, Any]:
    """Replace cli.import_dataset with a canned fake; return captured call kwargs."""
    captured: dict[str, Any] = {}

    def fake(
        path: str | Path, *, profile: bool = True, write_metadata: bool = True
    ) -> tuple[pd.DataFrame, ImportReport]:
        captured["path"] = path
        captured["profile"] = profile
        captured["write_metadata"] = write_metadata
        return pd.DataFrame({"id": [1, 2]}), report

    monkeypatch.setattr(cli, "import_dataset", fake)
    return captured


def test_scan_clean_renders_summary_and_profiles(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    report = make_report(
        tmp_path,
        diagnostics=[
            Diagnostic(
                code="DUPLICATE_ROWS",
                severity=Severity.WARNING,
                message="1 duplicate row found",
                file="sales.csv",
            )
        ],
    )
    patch_import(monkeypatch, report)

    result = runner.invoke(cli.app, ["scan", str(tmp_path)])

    assert result.exit_code == 0
    assert "Scan summary" in result.stdout
    assert "Files ingested: 1" in result.stdout
    assert "Total rows: 4" in result.stdout
    # Profile table content
    assert "sales.csv" in result.stdout
    assert "int64" in result.stdout
    assert "ada" in result.stdout
    # Diagnostic line
    assert "DUPLICATE_ROWS" in result.stdout
    assert "1 duplicate row found" in result.stdout


def test_scan_json_output_matches_to_dict(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    report = make_report(tmp_path)
    patch_import(monkeypatch, report)

    result = runner.invoke(cli.app, ["scan", str(tmp_path), "--json"])

    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed == report.to_dict()
    assert "Scan summary" not in result.stdout


def test_scan_exit_1_on_error_diagnostic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    report = make_report(
        tmp_path,
        diagnostics=[
            Diagnostic(
                code="INGESTION_FAILED",
                severity=Severity.ERROR,
                message="could not parse file",
                file="sales.csv",
            )
        ],
    )
    patch_import(monkeypatch, report)

    result = runner.invoke(cli.app, ["scan", str(tmp_path)])

    assert result.exit_code == 1
    assert "INGESTION_FAILED" in result.stdout
    assert "could not parse file" in result.stdout


def test_scan_exit_2_on_smartdataranger_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake(path: str | Path, **kwargs: Any) -> tuple[pd.DataFrame, ImportReport]:
        raise SmartDataRangerError("boom: unreadable dataset")

    monkeypatch.setattr(cli, "import_dataset", fake)

    result = runner.invoke(cli.app, ["scan", str(tmp_path)])

    assert result.exit_code == 2
    assert "boom: unreadable dataset" in result.stderr
    assert "boom: unreadable dataset" not in result.stdout


def test_scan_forwards_flags(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    report = make_report(tmp_path, with_profiles=False)
    captured = patch_import(monkeypatch, report)

    result = runner.invoke(cli.app, ["scan", str(tmp_path), "--no-profile", "--no-write-metadata"])

    assert result.exit_code == 0
    assert captured["profile"] is False
    assert captured["write_metadata"] is False
    assert captured["path"] == tmp_path


def test_scan_forwards_default_flags(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    report = make_report(tmp_path, with_profiles=False)
    captured = patch_import(monkeypatch, report)

    result = runner.invoke(cli.app, ["scan", str(tmp_path)])

    assert result.exit_code == 0
    assert captured["profile"] is True
    assert captured["write_metadata"] is True
