"""Tests for smartdataranger.loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from smartdataranger.errors import IngestionError, MetadataError
from smartdataranger.loader import load_dataframe, load_dataset, load_metadata
from smartdataranger.models import FileMetadata


def _write_workspace(tmp_path: Path, records: list[dict[str, Any]]) -> Path:
    """Write a metadata.json under <tmp_path>/.smartdataranger and return its path."""
    output_dir = tmp_path / ".smartdataranger"
    output_dir.mkdir()
    metadata_file = output_dir / "metadata.json"
    metadata_file.write_text(json.dumps(records), encoding="utf-8")
    return metadata_file


def _csv_record(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "file_name": "sample.csv",
        "file_type": ".csv",
        "reader": "csv",
        "reader_kwargs": {},
        "columns": ["id", "name", "score"],
        "row_count": 4,
        "source": "sample.csv",
    }
    record.update(overrides)
    return record


class TestLoadMetadata:
    def test_parses_records(self, tmp_path: Path) -> None:
        metadata_file = _write_workspace(tmp_path, [_csv_record()])
        records = load_metadata(metadata_file)
        assert len(records) == 1
        assert records[0] == FileMetadata.from_dict(_csv_record())

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(MetadataError, match="Cannot read"):
            load_metadata(tmp_path / "metadata.json")

    def test_malformed_json(self, tmp_path: Path) -> None:
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(MetadataError, match="Invalid JSON"):
            load_metadata(metadata_file)

    def test_non_list_payload(self, tmp_path: Path) -> None:
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text(json.dumps({"files": []}), encoding="utf-8")
        with pytest.raises(MetadataError, match="must contain a JSON list"):
            load_metadata(metadata_file)

    def test_non_dict_record(self, tmp_path: Path) -> None:
        metadata_file = _write_workspace(tmp_path, ["not-a-dict"])  # type: ignore[list-item]
        with pytest.raises(MetadataError, match="must be an object"):
            load_metadata(metadata_file)

    def test_record_malformed_field_type(self, tmp_path: Path) -> None:
        metadata_file = _write_workspace(tmp_path, [_csv_record(columns=None)])
        with pytest.raises(MetadataError, match="malformed field"):
            load_metadata(metadata_file)

    def test_record_missing_required_key(self, tmp_path: Path) -> None:
        record = _csv_record()
        del record["reader"]
        metadata_file = _write_workspace(tmp_path, [record])
        with pytest.raises(MetadataError, match="missing required key"):
            load_metadata(metadata_file)


class TestLoadDataframe:
    def test_unknown_reader_key_rejected(self, tmp_path: Path) -> None:
        """The eval-class attack surface is dead: only READERS keys execute."""
        meta = FileMetadata.from_dict(_csv_record(reader="__import__('os').system"))
        with pytest.raises(MetadataError, match="unknown reader"):
            load_dataframe(meta, tmp_path)

    def test_absolute_source_rejected(self, tmp_path: Path) -> None:
        meta = FileMetadata.from_dict(_csv_record(source="/etc/passwd"))
        with pytest.raises(MetadataError, match="outside the dataset root"):
            load_dataframe(meta, tmp_path)

    def test_traversal_source_rejected(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        meta = FileMetadata.from_dict(_csv_record(source="../escape.csv"))
        with pytest.raises(MetadataError, match="outside the dataset root"):
            load_dataframe(meta, root)

    def test_missing_source_file(self, tmp_path: Path) -> None:
        meta = FileMetadata.from_dict(_csv_record(source="missing.csv"))
        with pytest.raises(IngestionError):
            load_dataframe(meta, tmp_path)

    def test_reader_kwargs_forwarded(self, tmp_path: Path, sample_frame: pd.DataFrame) -> None:
        path = tmp_path / "semi.csv"
        sample_frame.to_csv(path, index=False, sep=";")
        meta = FileMetadata.from_dict(
            _csv_record(file_name="semi.csv", source="semi.csv", reader_kwargs={"sep": ";"})
        )
        frame = load_dataframe(meta, tmp_path)
        pd.testing.assert_frame_equal(frame, sample_frame)


class TestLoadDataset:
    def test_round_trip(self, tmp_path: Path, sample_frame: pd.DataFrame) -> None:
        sample_frame.to_csv(tmp_path / "sample.csv", index=False)
        metadata_file = _write_workspace(tmp_path, [_csv_record()])
        frames = load_dataset(metadata_file)
        assert set(frames) == {"sample.csv"}
        pd.testing.assert_frame_equal(frames["sample.csv"], sample_frame)

    def test_explicit_root(self, tmp_path: Path, sample_frame: pd.DataFrame) -> None:
        root = tmp_path / "data"
        root.mkdir()
        sample_frame.to_csv(root / "sample.csv", index=False)
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text(json.dumps([_csv_record()]), encoding="utf-8")
        frames = load_dataset(metadata_file, root=root)
        pd.testing.assert_frame_equal(frames["sample.csv"], sample_frame)

    def test_injected_reader_fails_cleanly(self, tmp_path: Path) -> None:
        metadata_file = _write_workspace(tmp_path, [_csv_record(reader="__import__('os').system")])
        with pytest.raises(MetadataError, match="unknown reader"):
            load_dataset(metadata_file)
