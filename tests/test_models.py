"""Tests for the shared data contracts in smartdataranger.models."""

from __future__ import annotations

import json
from pathlib import Path

from smartdataranger.models import (
    ColumnProfile,
    Diagnostic,
    FileMetadata,
    FileReport,
    ImportReport,
    Severity,
)


def _metadata(**overrides: object) -> FileMetadata:
    kwargs: dict = {
        "file_name": "sales.csv",
        "file_type": ".csv",
        "reader": "csv",
        "reader_kwargs": {"sep": ";", "encoding": "latin-1"},
        "columns": ["id", "name"],
        "row_count": 42,
        "source": "sales.csv",
    }
    kwargs.update(overrides)
    return FileMetadata(**kwargs)


def _diag(code: str, severity: Severity, file: str = "") -> Diagnostic:
    return Diagnostic(code=code, severity=severity, message=f"{code} found", file=file)


class TestFileMetadata:
    def test_to_dict_from_dict_round_trip(self) -> None:
        meta = _metadata()
        assert FileMetadata.from_dict(meta.to_dict()) == meta

    def test_to_dict_returns_independent_copy(self) -> None:
        meta = _metadata()
        data = meta.to_dict()
        data["reader_kwargs"]["sep"] = ","
        data["columns"].append("extra")
        assert meta.reader_kwargs == {"sep": ";", "encoding": "latin-1"}
        assert meta.columns == ["id", "name"]

    def test_from_dict_copies_mutable_input(self) -> None:
        data = _metadata().to_dict()
        meta = FileMetadata.from_dict(data)
        data["reader_kwargs"]["sep"] = ","
        data["columns"].append("extra")
        assert meta.reader_kwargs == {"sep": ";", "encoding": "latin-1"}
        assert meta.columns == ["id", "name"]

    def test_from_dict_defaults_missing_reader_kwargs(self) -> None:
        data = _metadata().to_dict()
        del data["reader_kwargs"]
        assert FileMetadata.from_dict(data).reader_kwargs == {}


class TestImportReport:
    def test_all_diagnostics_dataset_level_first_then_per_file(self) -> None:
        d_dataset = _diag("EMPTY_DATASET", Severity.WARNING)
        d_f1a = _diag("ENCODING_NON_UTF8", Severity.WARNING, file="a.csv")
        d_f1b = _diag("DELIMITER_SNIFFED", Severity.INFO, file="a.csv")
        d_f2 = _diag("ALL_NULL_COLUMN", Severity.WARNING, file="b.csv")
        report = ImportReport(
            root=Path("/data"),
            files=[
                FileReport(metadata=_metadata(file_name="a.csv"), diagnostics=[d_f1a, d_f1b]),
                FileReport(metadata=_metadata(file_name="b.csv"), diagnostics=[d_f2]),
            ],
            diagnostics=[d_dataset],
        )
        assert report.all_diagnostics == [d_dataset, d_f1a, d_f1b, d_f2]

    def test_has_errors_false_without_error_severity(self) -> None:
        report = ImportReport(
            root=Path("/data"),
            files=[
                FileReport(
                    metadata=_metadata(),
                    diagnostics=[_diag("DELIMITER_SNIFFED", Severity.INFO, file="sales.csv")],
                )
            ],
            diagnostics=[_diag("EMPTY_DATASET", Severity.WARNING)],
        )
        assert report.has_errors() is False

    def test_has_errors_true_with_error_severity_in_file(self) -> None:
        report = ImportReport(
            root=Path("/data"),
            files=[
                FileReport(
                    metadata=_metadata(),
                    diagnostics=[_diag("INGESTION_FAILED", Severity.ERROR, file="sales.csv")],
                )
            ],
        )
        assert report.has_errors() is True

    def test_has_errors_true_with_dataset_level_error(self) -> None:
        report = ImportReport(
            root=Path("/data"),
            diagnostics=[_diag("EMPTY_DATASET", Severity.ERROR)],
        )
        assert report.has_errors() is True

    def test_empty_report_has_no_errors(self) -> None:
        report = ImportReport(root=Path("/data"))
        assert report.all_diagnostics == []
        assert report.has_errors() is False

    def test_to_dict_is_json_serializable(self) -> None:
        profile = ColumnProfile(
            name="id",
            dtype="int64",
            non_null_count=42,
            null_count=0,
            null_pct=0.0,
            unique_count=42,
            cardinality_pct=100.0,
            sample_values=["1", "2", "3"],
        )
        report = ImportReport(
            root=Path("/data"),
            files=[
                FileReport(
                    metadata=_metadata(),
                    diagnostics=[_diag("ENCODING_NON_UTF8", Severity.WARNING, file="sales.csv")],
                    column_profiles=[profile],
                    duplicate_row_count=1,
                )
            ],
            diagnostics=[_diag("EMPTY_DATASET", Severity.INFO)],
        )
        payload = report.to_dict()
        round_tripped = json.loads(json.dumps(payload))
        assert round_tripped["root"] == "/data"
        assert round_tripped["diagnostics"][0]["severity"] == "info"
        file_entry = round_tripped["files"][0]
        assert file_entry["metadata"]["file_name"] == "sales.csv"
        assert file_entry["diagnostics"][0]["code"] == "ENCODING_NON_UTF8"
        assert file_entry["column_profiles"][0]["name"] == "id"
        assert file_entry["duplicate_row_count"] == 1


def test_severity_values() -> None:
    assert Severity.INFO == "info"
    assert Severity.WARNING == "warning"
    assert Severity.ERROR == "error"
