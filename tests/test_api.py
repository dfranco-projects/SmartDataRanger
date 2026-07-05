"""Unit tests for the import_dataset flagship API.

Collaborator modules (paths, ingest, loader, diagnostics, profiling) are
NotImplementedError stubs, so every orchestrated call is monkeypatched on the
``smartdataranger.api`` module namespace.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

import smartdataranger.api as api
from smartdataranger.errors import IngestionError
from smartdataranger.models import (
    ColumnProfile,
    Diagnostic,
    FileMetadata,
    ImportReport,
    Severity,
)
from smartdataranger.paths import WorkspacePaths


def make_meta(name: str) -> FileMetadata:
    return FileMetadata(
        file_name=name,
        file_type=".csv",
        reader="csv",
        reader_kwargs={},
        columns=["id", "name"],
        row_count=3,
        source=name,
    )


def make_paths(root: Path) -> WorkspacePaths:
    output_dir = root / ".smartdataranger"
    return WorkspacePaths(
        root=root,
        output_dir=output_dir,
        metadata_file=output_dir / "metadata.json",
        extracted_dir=output_dir / "extracted",
    )


def make_profile(name: str) -> ColumnProfile:
    return ColumnProfile(
        name=name,
        dtype="int64",
        non_null_count=3,
        null_count=0,
        null_pct=0.0,
        unique_count=3,
        cardinality_pct=100.0,
        sample_values=["1", "2", "3"],
    )


@pytest.fixture
def frame() -> pd.DataFrame:
    return pd.DataFrame({"id": [1, 2, 3], "name": ["ada", "grace", "alan"]})


def patch_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    metadata: list[FileMetadata],
    dataset_diagnostics: list[Diagnostic] | None = None,
    frames: dict[str, pd.DataFrame] | None = None,
    duplicate_counts: dict[str, int] | None = None,
) -> dict[str, list[Any]]:
    """Patch every collaborator on the api module; return per-function call logs."""
    calls: dict[str, list[Any]] = {
        "resolve_workspace": [],
        "ingest_directory": [],
        "load_dataframe": [],
        "diagnose_frame": [],
        "profile_columns": [],
        "count_duplicate_rows": [],
    }
    loaded = frames or {}
    duplicates = duplicate_counts or {}

    def fake_resolve_workspace(data_dir: str | Path) -> WorkspacePaths:
        calls["resolve_workspace"].append(Path(data_dir))
        return make_paths(Path(data_dir))

    def fake_ingest_directory(
        paths: WorkspacePaths, *, write_metadata: bool = True
    ) -> tuple[list[FileMetadata], list[Diagnostic]]:
        calls["ingest_directory"].append({"paths": paths, "write_metadata": write_metadata})
        return list(metadata), list(dataset_diagnostics or [])

    def fake_load_dataframe(meta: FileMetadata, root: Path) -> pd.DataFrame:
        calls["load_dataframe"].append(meta.file_name)
        if meta.file_name not in loaded:
            raise IngestionError(f"cannot read {meta.file_name}")
        return loaded[meta.file_name]

    def fake_diagnose_frame(df: pd.DataFrame, file_name: str) -> list[Diagnostic]:
        calls["diagnose_frame"].append(file_name)
        return []

    def fake_profile_columns(df: pd.DataFrame) -> list[ColumnProfile]:
        calls["profile_columns"].append(list(df.columns))
        return [make_profile(str(col)) for col in df.columns]

    def fake_count_duplicate_rows(df: pd.DataFrame) -> int:
        calls["count_duplicate_rows"].append(len(df))
        for name, loaded_df in loaded.items():
            if loaded_df is df:
                return duplicates.get(name, 0)
        return 0

    monkeypatch.setattr(api, "resolve_workspace", fake_resolve_workspace)
    monkeypatch.setattr(api, "ingest_directory", fake_ingest_directory)
    monkeypatch.setattr(api, "load_dataframe", fake_load_dataframe)
    monkeypatch.setattr(api, "diagnose_frame", fake_diagnose_frame)
    monkeypatch.setattr(api, "profile_columns", fake_profile_columns)
    monkeypatch.setattr(api, "count_duplicate_rows", fake_count_duplicate_rows)
    return calls


def test_single_file_returns_bare_dataframe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, frame: pd.DataFrame
) -> None:
    patch_pipeline(monkeypatch, metadata=[make_meta("a.csv")], frames={"a.csv": frame})

    result, report = api.import_dataset(tmp_path)

    assert isinstance(result, pd.DataFrame)
    pd.testing.assert_frame_equal(result, frame)
    assert isinstance(report, ImportReport)
    assert report.root == tmp_path
    assert [f.metadata.file_name for f in report.files] == ["a.csv"]
    assert not report.has_errors()


def test_multiple_files_return_dict_keyed_by_file_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, frame: pd.DataFrame
) -> None:
    other = frame.head(1)
    patch_pipeline(
        monkeypatch,
        metadata=[make_meta("a.csv"), make_meta("b.csv")],
        frames={"a.csv": frame, "b.csv": other},
    )

    result, report = api.import_dataset(tmp_path)

    assert isinstance(result, dict)
    assert set(result) == {"a.csv", "b.csv"}
    pd.testing.assert_frame_equal(result["a.csv"], frame)
    pd.testing.assert_frame_equal(result["b.csv"], other)
    assert len(report.files) == 2


def test_profiling_populates_file_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, frame: pd.DataFrame
) -> None:
    patch_pipeline(
        monkeypatch,
        metadata=[make_meta("a.csv")],
        frames={"a.csv": frame},
        duplicate_counts={"a.csv": 2},
    )

    _, report = api.import_dataset(tmp_path)

    file_report = report.files[0]
    assert [p.name for p in file_report.column_profiles] == ["id", "name"]
    assert file_report.duplicate_row_count == 2
    dup = [d for d in file_report.diagnostics if d.code == "DUPLICATE_ROWS"]
    assert len(dup) == 1
    assert dup[0].severity is Severity.INFO
    assert dup[0].detail["duplicate_row_count"] == 2


def test_no_duplicate_rows_diagnostic_when_count_is_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, frame: pd.DataFrame
) -> None:
    patch_pipeline(monkeypatch, metadata=[make_meta("a.csv")], frames={"a.csv": frame})

    _, report = api.import_dataset(tmp_path)

    assert report.files[0].duplicate_row_count == 0
    assert all(d.code != "DUPLICATE_ROWS" for d in report.files[0].diagnostics)


def test_profile_false_skips_profiling_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, frame: pd.DataFrame
) -> None:
    calls = patch_pipeline(monkeypatch, metadata=[make_meta("a.csv")], frames={"a.csv": frame})

    result, report = api.import_dataset(tmp_path, profile=False)

    assert isinstance(result, pd.DataFrame)
    assert calls["diagnose_frame"] == []
    assert calls["profile_columns"] == []
    assert calls["count_duplicate_rows"] == []
    assert report.files[0].column_profiles == []
    assert report.files[0].duplicate_row_count == 0


def test_load_failure_records_ingestion_failed_and_skips_frame(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, frame: pd.DataFrame
) -> None:
    calls = patch_pipeline(
        monkeypatch,
        metadata=[make_meta("good.csv"), make_meta("bad.csv")],
        frames={"good.csv": frame},  # bad.csv raises IngestionError
    )

    result, report = api.import_dataset(tmp_path)

    # Only one frame loaded, so bare DataFrame return shape.
    assert isinstance(result, pd.DataFrame)
    assert calls["load_dataframe"] == ["good.csv", "bad.csv"]
    bad_report = next(f for f in report.files if f.metadata.file_name == "bad.csv")
    failures = [d for d in bad_report.diagnostics if d.code == "INGESTION_FAILED"]
    assert len(failures) == 1
    assert failures[0].severity is Severity.ERROR
    assert failures[0].file == "bad.csv"
    # Failed file is never profiled.
    assert calls["diagnose_frame"] == ["good.csv"]
    assert report.has_errors()


def test_all_failures_return_empty_dict_without_empty_dataset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    patch_pipeline(monkeypatch, metadata=[make_meta("bad.csv")], frames={})

    result, report = api.import_dataset(tmp_path)

    assert result == {}
    assert all(d.code != "EMPTY_DATASET" for d in report.diagnostics)
    assert report.has_errors()


def test_empty_folder_adds_empty_dataset_diagnostic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    patch_pipeline(monkeypatch, metadata=[])

    result, report = api.import_dataset(tmp_path)

    assert result == {}
    assert report.files == []
    empty = [d for d in report.diagnostics if d.code == "EMPTY_DATASET"]
    assert len(empty) == 1
    assert empty[0].severity is Severity.WARNING
    assert empty[0].file == ""
    assert not report.has_errors()


def test_write_metadata_flag_is_forwarded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, frame: pd.DataFrame
) -> None:
    calls = patch_pipeline(monkeypatch, metadata=[make_meta("a.csv")], frames={"a.csv": frame})

    api.import_dataset(tmp_path, write_metadata=False)
    api.import_dataset(tmp_path, write_metadata=True)

    assert [c["write_metadata"] for c in calls["ingest_directory"]] == [False, True]
    assert calls["ingest_directory"][0]["paths"].root == tmp_path


def test_dataset_level_diagnostics_flow_into_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, frame: pd.DataFrame
) -> None:
    skipped = Diagnostic(
        code="UNSUPPORTED_FILE_SKIPPED",
        severity=Severity.WARNING,
        message="skipped notes.docx",
        file="notes.docx",
    )
    patch_pipeline(
        monkeypatch,
        metadata=[make_meta("a.csv")],
        dataset_diagnostics=[skipped],
        frames={"a.csv": frame},
    )

    _, report = api.import_dataset(tmp_path)

    assert skipped in report.diagnostics
    assert skipped in report.all_diagnostics
    assert not report.has_errors()


def test_single_file_path_filters_to_that_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, frame: pd.DataFrame
) -> None:
    target = tmp_path / "a.csv"
    target.write_text("id,name\n1,ada\n")
    other_diag = Diagnostic(
        code="INGESTION_FAILED",
        severity=Severity.ERROR,
        message="broken",
        file="b.csv",
    )
    calls = patch_pipeline(
        monkeypatch,
        metadata=[make_meta("a.csv"), make_meta("b.csv")],
        dataset_diagnostics=[other_diag],
        frames={"a.csv": frame, "b.csv": frame.head(1)},
    )

    result, report = api.import_dataset(target)

    # Workspace root is the file's parent directory.
    assert calls["resolve_workspace"] == [tmp_path]
    assert report.root == tmp_path
    # Only the named file is processed and returned.
    assert isinstance(result, pd.DataFrame)
    pd.testing.assert_frame_equal(result, frame)
    assert [f.metadata.file_name for f in report.files] == ["a.csv"]
    assert calls["load_dataframe"] == ["a.csv"]
    # Diagnostics about other files are dropped.
    assert other_diag not in report.diagnostics
    assert not report.has_errors()


def test_accepts_string_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, frame: pd.DataFrame
) -> None:
    calls = patch_pipeline(monkeypatch, metadata=[make_meta("a.csv")], frames={"a.csv": frame})

    result, _ = api.import_dataset(str(tmp_path))

    assert isinstance(result, pd.DataFrame)
    assert calls["resolve_workspace"] == [tmp_path]
