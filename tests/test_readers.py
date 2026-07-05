"""Tests for the whitelisted reader dispatch (the eval() replacement)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from smartdataranger.errors import IngestionError, UnsupportedFormatError
from smartdataranger.readers import (
    EXTENSION_TO_READER,
    READERS,
    SUPPORTED_EXTENSIONS,
    read_file,
    reader_for_extension,
)

# Every READERS key must map to a conftest fixture producing a file for it.
FIXTURE_BY_READER = {
    "csv": "sample_csv",
    "excel": "sample_xlsx",
    "parquet": "sample_parquet",
    "json": "sample_json",
    "txt": "sample_txt",
}

EXPECTED_COLUMNS = ["id", "name", "score"]
EXPECTED_SHAPE = (4, 3)


def test_fixture_map_covers_every_reader() -> None:
    assert set(FIXTURE_BY_READER) == set(READERS)


@pytest.mark.parametrize("key", sorted(READERS))
def test_read_file_every_reader(key: str, request: pytest.FixtureRequest) -> None:
    path = request.getfixturevalue(FIXTURE_BY_READER[key])
    df = read_file(path, key)
    assert df.shape == EXPECTED_SHAPE
    assert list(df.columns) == EXPECTED_COLUMNS


def test_txt_reader_parses_tabs_not_json(sample_txt: Path) -> None:
    """The legacy bug read .txt files with pd.read_json; the tab-separated
    fixture must parse into the real tabular shape via the csv reader."""
    df = read_file(sample_txt, "txt")
    assert df.shape == EXPECTED_SHAPE
    assert list(df.columns) == EXPECTED_COLUMNS
    assert list(df["name"]) == ["ada", "grace", "alan", "alan"]


def test_kwargs_override_default_kwargs(tmp_path: Path) -> None:
    path = tmp_path / "semi.txt"
    path.write_text("a;b\n1;2\n", encoding="utf-8")
    # Without the override, the txt reader's default sep="\t" yields one column.
    assert read_file(path, "txt").shape == (1, 1)
    # sep=";" must win over the default.
    df = read_file(path, "txt", sep=";")
    assert list(df.columns) == ["a", "b"]
    assert df.shape == (1, 2)


def test_kwargs_passed_to_reader_without_defaults(tmp_path: Path) -> None:
    path = tmp_path / "semi.csv"
    path.write_text("a;b\n1;2\n", encoding="utf-8")
    df = read_file(path, "csv", sep=";")
    assert list(df.columns) == ["a", "b"]
    assert df.shape == (1, 2)


def test_unknown_reader_key_raises(sample_csv: Path) -> None:
    with pytest.raises(UnsupportedFormatError):
        read_file(sample_csv, "yaml")


def test_reader_for_extension_known() -> None:
    for extension, key in EXTENSION_TO_READER.items():
        assert reader_for_extension(extension) is READERS[key]
    # Lookup is case-insensitive.
    assert reader_for_extension(".CSV") is READERS["csv"]


def test_reader_for_extension_unknown_raises() -> None:
    with pytest.raises(UnsupportedFormatError):
        reader_for_extension(".xyz")


def test_supported_extensions_include_zip_and_all_reader_extensions() -> None:
    assert ".zip" in SUPPORTED_EXTENSIONS
    assert set(EXTENSION_TO_READER) <= SUPPORTED_EXTENSIONS
    assert set(EXTENSION_TO_READER.values()) <= set(READERS)


def test_underlying_failure_wrapped_in_ingestion_error(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.parquet"
    path.write_bytes(b"this is definitely not a parquet file")
    with pytest.raises(IngestionError) as excinfo:
        read_file(path, "parquet")
    assert excinfo.value.__cause__ is not None
    assert isinstance(excinfo.value.__cause__, Exception)


def test_read_file_returns_dataframe(sample_csv: Path) -> None:
    assert isinstance(read_file(sample_csv, "csv"), pd.DataFrame)
