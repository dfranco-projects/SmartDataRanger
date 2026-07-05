"""Tests for the deterministic diagnostics rules engine."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from smartdataranger.diagnostics import (
    detect_encoding,
    diagnose_file,
    diagnose_frame,
    sniff_delimiter,
)
from smartdataranger.models import Diagnostic, Severity


def _codes(diagnostics: list[Diagnostic]) -> set[str]:
    return {d.code for d in diagnostics}


def _by_code(diagnostics: list[Diagnostic], code: str) -> Diagnostic:
    return next(d for d in diagnostics if d.code == code)


class TestDetectEncoding:
    def test_utf8_file(self, sample_csv: Path) -> None:
        encoding, confidence = detect_encoding(sample_csv)
        assert encoding is not None
        assert encoding.lower().replace("-", "_") in {"utf_8", "ascii"}
        assert 0.0 <= confidence <= 1.0

    def test_latin1_file(self, messy_csv: Path) -> None:
        encoding, confidence = detect_encoding(messy_csv)
        assert encoding is not None
        assert encoding.lower().replace("-", "_") not in {"utf_8", "ascii"}
        # The detected codec must round-trip the file's bytes.
        messy_csv.read_bytes().decode(encoding)
        assert 0.0 < confidence <= 1.0

    def test_missing_file(self, tmp_path: Path) -> None:
        assert detect_encoding(tmp_path / "nope.csv") == (None, 0.0)


class TestSniffDelimiter:
    def test_comma(self, sample_csv: Path) -> None:
        assert sniff_delimiter(sample_csv) == ","

    def test_tab(self, sample_txt: Path) -> None:
        assert sniff_delimiter(sample_txt) == "\t"

    def test_semicolon_latin1(self, messy_csv: Path) -> None:
        assert sniff_delimiter(messy_csv, encoding="latin-1") == ";"

    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.csv"
        path.write_text("")
        assert sniff_delimiter(path) is None

    def test_no_delimiter(self, tmp_path: Path) -> None:
        path = tmp_path / "plain.txt"
        path.write_text("word\nword\nword\n")
        assert sniff_delimiter(path) is None

    def test_prose_does_not_over_trigger(self, tmp_path: Path) -> None:
        path = tmp_path / "prose.txt"
        path.write_text("hello world\nthe pipe | is | here\nplain line\n")
        assert sniff_delimiter(path) is None


class TestDiagnoseFile:
    def test_messy_csv(self, messy_csv: Path, tmp_path: Path) -> None:
        diagnostics, hints = diagnose_file(messy_csv, tmp_path)

        assert _codes(diagnostics) == {
            "ENCODING_NON_UTF8",
            "DELIMITER_SNIFFED",
            "MALFORMED_ROWS",
        }

        enc = _by_code(diagnostics, "ENCODING_NON_UTF8")
        assert enc.severity is Severity.WARNING
        assert enc.file == "messy.csv"
        assert enc.detail["encoding"] == hints["encoding"]

        delim = _by_code(diagnostics, "DELIMITER_SNIFFED")
        assert delim.severity is Severity.INFO
        assert delim.detail["delimiter"] == ";"

        rows = _by_code(diagnostics, "MALFORMED_ROWS")
        assert rows.severity is Severity.WARNING
        assert rows.detail == {"rows": [3], "expected": 3}

        assert hints["sep"] == ";"
        # The hints must make pandas parse the file correctly.
        df = pd.read_csv(messy_csv, **hints)
        assert list(df.columns) == ["ciudad", "país", "población"]

    def test_clean_csv(self, sample_csv: Path, tmp_path: Path) -> None:
        diagnostics, hints = diagnose_file(sample_csv, tmp_path)
        assert diagnostics == []
        assert hints == {}

    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.csv"
        path.write_text("")
        diagnostics, hints = diagnose_file(path, tmp_path)
        assert _codes(diagnostics) == {"EMPTY_FILE"}
        assert diagnostics[0].severity is Severity.ERROR
        assert hints == {}

    def test_whitespace_only_file(self, tmp_path: Path) -> None:
        path = tmp_path / "blank.csv"
        path.write_text("  \n\t\n")
        diagnostics, _ = diagnose_file(path, tmp_path)
        assert _codes(diagnostics) == {"EMPTY_FILE"}

    def test_whitespace_only_utf16_file(self, tmp_path: Path) -> None:
        path = tmp_path / "blank16.csv"
        path.write_text("  \n\t\n", encoding="utf-16")
        diagnostics, _ = diagnose_file(path, tmp_path)
        assert _codes(diagnostics) == {"EMPTY_FILE"}

    def test_oversized_field_does_not_crash(self, tmp_path: Path) -> None:
        path = tmp_path / "big.csv"
        path.write_text("a,b\n" + "x" * 200_000 + ",1\n")
        diagnostics, _ = diagnose_file(path, tmp_path)
        assert "MALFORMED_ROWS" not in _codes(diagnostics)

    def test_non_text_format_skipped(self, sample_parquet: Path, tmp_path: Path) -> None:
        diagnostics, hints = diagnose_file(sample_parquet, tmp_path)
        assert diagnostics == []
        assert hints == {}

    def test_relative_posix_path(self, tmp_path: Path) -> None:
        sub = tmp_path / "nested" / "dir"
        sub.mkdir(parents=True)
        path = sub / "empty.csv"
        path.write_text("")
        diagnostics, _ = diagnose_file(path, tmp_path)
        assert diagnostics[0].file == "nested/dir/empty.csv"


class TestDiagnoseFrame:
    def test_clean_frame(self, sample_frame: pd.DataFrame) -> None:
        assert diagnose_frame(sample_frame, "sample.csv") == []

    def test_duplicate_column_names(self) -> None:
        df = pd.DataFrame([[1, 2], [3, 4]])
        df.columns = ["a", "a"]
        diagnostics = diagnose_frame(df, "f.csv")
        dup = _by_code(diagnostics, "DUPLICATE_COLUMN_NAMES")
        assert dup.severity is Severity.WARNING
        assert dup.column == "a"
        assert dup.detail["count"] == 2

    def test_empty_column_name(self) -> None:
        df = pd.DataFrame({"": [1, 2], "  ": [3, 4], "ok": [5, 6]})
        diagnostics = diagnose_frame(df, "f.csv")
        empty = [d for d in diagnostics if d.code == "EMPTY_COLUMN_NAME"]
        assert {d.column for d in empty} == {"", "  "}
        assert all(d.severity is Severity.WARNING for d in empty)

    def test_unnamed_column(self) -> None:
        df = pd.DataFrame({"Unnamed: 0": [1, 2], "ok": [3, 4]})
        diagnostics = diagnose_frame(df, "f.csv")
        unnamed = _by_code(diagnostics, "EMPTY_COLUMN_NAME")
        assert unnamed.column == "Unnamed: 0"

    def test_mixed_type_column(self) -> None:
        df = pd.DataFrame({"m": pd.Series([1, "two", 3.0], dtype=object)})
        diagnostics = diagnose_frame(df, "f.csv")
        mixed = _by_code(diagnostics, "MIXED_TYPE_COLUMN")
        assert mixed.severity is Severity.WARNING
        assert mixed.column == "m"
        assert set(mixed.detail["types"]) == {"int", "str", "float"}

    def test_uniform_object_column_not_mixed(self) -> None:
        df = pd.DataFrame({"m": pd.Series(["a", "b", None], dtype=object)})
        assert "MIXED_TYPE_COLUMN" not in _codes(diagnose_frame(df, "f.csv"))

    def test_all_null_column(self) -> None:
        df = pd.DataFrame({"n": [None, None], "ok": [1, 2]})
        diagnostics = diagnose_frame(df, "f.csv")
        null = _by_code(diagnostics, "ALL_NULL_COLUMN")
        assert null.severity is Severity.WARNING
        assert null.column == "n"
        # An all-null column must not also be flagged constant.
        assert "CONSTANT_COLUMN" not in _codes(diagnostics)

    def test_constant_column(self) -> None:
        df = pd.DataFrame({"c": [7, 7, 7], "ok": [1, 2, 3]})
        diagnostics = diagnose_frame(df, "f.csv")
        const = _by_code(diagnostics, "CONSTANT_COLUMN")
        assert const.severity is Severity.INFO
        assert const.column == "c"

    def test_constant_skipped_for_single_row(self) -> None:
        df = pd.DataFrame({"c": [7], "ok": [1]})
        assert diagnose_frame(df, "f.csv") == []

    def test_zero_row_frame_not_all_null(self) -> None:
        df = pd.DataFrame({"a": pd.Series(dtype=float), "b": pd.Series(dtype=str)})
        assert diagnose_frame(df, "f.csv") == []

    def test_unhashable_values_do_not_crash(self) -> None:
        df = pd.DataFrame({"a": pd.Series([[1], [1]], dtype=object)})
        assert "CONSTANT_COLUMN" not in _codes(diagnose_frame(df, "f.csv"))
