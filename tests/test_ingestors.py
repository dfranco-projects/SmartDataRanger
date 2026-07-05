"""Tests for Unit 1: TabularIngestor, ZipIngestor, get_ingestor, ingest_directory."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from smartdataranger.errors import IngestionError, UnsupportedFormatError
from smartdataranger.ingest import Ingestor, get_ingestor, ingest_directory
from smartdataranger.ingest.ingestors import TabularIngestor, ZipIngestor
from smartdataranger.models import FileMetadata, Severity
from smartdataranger.paths import WorkspacePaths

EXPECTED_COLUMNS = ["id", "name", "score"]


def workspace(root: Path) -> WorkspacePaths:
    output_dir = root / ".smartdataranger"
    return WorkspacePaths(
        root=root,
        output_dir=output_dir,
        metadata_file=output_dir / "metadata.json",
        extracted_dir=output_dir / "extracted",
    )


@pytest.mark.parametrize(
    ("fixture", "file_type", "reader"),
    [
        ("sample_csv", ".csv", "csv"),
        ("sample_txt", ".txt", "txt"),
        ("sample_json", ".json", "json"),
        ("sample_xlsx", ".xlsx", "excel"),
        ("sample_parquet", ".parquet", "parquet"),
    ],
)
def test_tabular_formats_ingest_with_correct_metadata(
    request: pytest.FixtureRequest, tmp_path: Path, fixture: str, file_type: str, reader: str
) -> None:
    file_path: Path = request.getfixturevalue(fixture)
    metadata, diagnostics = ingest_directory(workspace(tmp_path), write_metadata=False)

    assert [d for d in diagnostics if d.severity is Severity.ERROR] == []
    assert len(metadata) == 1
    meta = metadata[0]
    assert meta.file_name == file_path.name
    assert meta.file_type == file_type
    assert meta.reader == reader
    assert meta.columns == EXPECTED_COLUMNS
    assert meta.row_count == 4
    assert meta.source == file_path.name  # POSIX path relative to root


def test_tabular_ingestor_satisfies_protocol() -> None:
    assert isinstance(TabularIngestor(".csv"), Ingestor)
    assert isinstance(ZipIngestor(extracted_dir=Path("unused")), Ingestor)


def test_tabular_ingestor_rejects_unknown_extension() -> None:
    with pytest.raises(UnsupportedFormatError):
        TabularIngestor(".pdf")


def test_get_ingestor_registry(tmp_path: Path) -> None:
    assert isinstance(get_ingestor(".zip", extracted_dir=tmp_path), ZipIngestor)
    for ext in (".csv", ".xlsx", ".xls", ".parquet", ".json", ".txt", ".CSV"):
        assert isinstance(get_ingestor(ext, extracted_dir=tmp_path), TabularIngestor)
    with pytest.raises(UnsupportedFormatError):
        get_ingestor(".pdf", extracted_dir=tmp_path)


def test_zip_extraction_and_member_metadata(tmp_path: Path, sample_zip: Path) -> None:
    paths = workspace(tmp_path)
    metadata, diagnostics = ingest_directory(paths, write_metadata=False)

    assert [d for d in diagnostics if d.severity is Severity.ERROR] == []
    assert {m.file_name for m in metadata} == {"inner_a.csv", "inner_b.csv"}
    by_name = {m.file_name: m for m in metadata}
    assert by_name["inner_a.csv"].row_count == 4
    assert by_name["inner_b.csv"].row_count == 2
    for meta in metadata:
        assert meta.file_type == ".csv"
        assert meta.reader == "csv"
        assert meta.columns == EXPECTED_COLUMNS
        assert meta.source == f".smartdataranger/extracted/{meta.file_name}"
        assert (paths.root / meta.source).is_file()


def test_zip_slip_member_is_rejected(tmp_path: Path) -> None:
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../escape.csv", "a,b\n1,2\n")

    paths = workspace(tmp_path)
    with pytest.raises(IngestionError, match="zip-slip"):
        ZipIngestor(extracted_dir=paths.extracted_dir).ingest(evil, paths.root)
    assert not (paths.output_dir / "escape.csv").exists()

    # Through the orchestrator it becomes a diagnostic, never an exception.
    metadata, diagnostics = ingest_directory(paths, write_metadata=False)
    assert metadata == []
    assert [d.code for d in diagnostics] == ["INGESTION_FAILED"]
    assert diagnostics[0].severity is Severity.ERROR
    assert diagnostics[0].file == "evil.zip"


def test_zip_with_unsupported_member(tmp_path: Path) -> None:
    archive = tmp_path / "mixed.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("ok.csv", "a,b\n1,2\n")
        zf.writestr("notes.md", "# hello\n")

    metadata, diagnostics = ingest_directory(workspace(tmp_path), write_metadata=False)
    assert [m.file_name for m in metadata] == ["ok.csv"]
    skipped = [d for d in diagnostics if d.code == "UNSUPPORTED_FILE_SKIPPED"]
    assert len(skipped) == 1
    assert skipped[0].severity is Severity.INFO
    assert skipped[0].file == ".smartdataranger/extracted/notes.md"


def test_zip_with_corrupt_member_keeps_good_members(tmp_path: Path) -> None:
    archive = tmp_path / "partial.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("ok.csv", "a,b\n1,2\n")
        zf.writestr("corrupt.parquet", "\x00\x01 not parquet")

    metadata, diagnostics = ingest_directory(workspace(tmp_path), write_metadata=False)
    assert [m.file_name for m in metadata] == ["ok.csv"]
    failed = [d for d in diagnostics if d.code == "INGESTION_FAILED"]
    assert len(failed) == 1
    assert failed[0].file == ".smartdataranger/extracted/corrupt.parquet"


def test_bad_zip_records_ingestion_failed(tmp_path: Path) -> None:
    (tmp_path / "broken.zip").write_bytes(b"not a zip archive")
    metadata, diagnostics = ingest_directory(workspace(tmp_path), write_metadata=False)
    assert metadata == []
    assert [d.code for d in diagnostics] == ["INGESTION_FAILED"]


def test_unsupported_file_skipped_diagnostic(tmp_path: Path, sample_csv: Path) -> None:
    (tmp_path / "readme.pdf").write_bytes(b"%PDF-1.4")
    metadata, diagnostics = ingest_directory(workspace(tmp_path), write_metadata=False)

    assert [m.file_name for m in metadata] == ["sample.csv"]
    skipped = [d for d in diagnostics if d.code == "UNSUPPORTED_FILE_SKIPPED"]
    assert len(skipped) == 1
    assert skipped[0].severity is Severity.INFO
    assert skipped[0].file == "readme.pdf"


def test_bad_file_records_ingestion_failed_and_run_continues(
    tmp_path: Path, sample_csv: Path
) -> None:
    (tmp_path / "corrupt.parquet").write_bytes(b"\x00\x01 definitely not parquet")
    metadata, diagnostics = ingest_directory(workspace(tmp_path), write_metadata=False)

    assert [m.file_name for m in metadata] == ["sample.csv"]
    failed = [d for d in diagnostics if d.code == "INGESTION_FAILED"]
    assert len(failed) == 1
    assert failed[0].severity is Severity.ERROR
    assert failed[0].file == "corrupt.parquet"


def test_hidden_and_underscore_files_skipped(tmp_path: Path) -> None:
    (tmp_path / ".hidden.csv").write_text("a\n1\n", encoding="utf-8")
    (tmp_path / "_cache.csv").write_text("a\n1\n", encoding="utf-8")
    (tmp_path / "subdir").mkdir()

    metadata, diagnostics = ingest_directory(workspace(tmp_path), write_metadata=False)
    assert metadata == []
    assert diagnostics == []


def test_metadata_json_written_and_round_trips(tmp_path: Path, sample_csv: Path) -> None:
    paths = workspace(tmp_path)
    metadata, _ = ingest_directory(paths)

    assert paths.metadata_file.is_file()
    entries = json.loads(paths.metadata_file.read_text(encoding="utf-8"))
    assert isinstance(entries, list)
    restored = [FileMetadata.from_dict(e) for e in entries]
    assert restored == metadata


def test_write_metadata_false_writes_nothing(tmp_path: Path, sample_csv: Path) -> None:
    paths = workspace(tmp_path)
    ingest_directory(paths, write_metadata=False)
    assert not paths.metadata_file.exists()
