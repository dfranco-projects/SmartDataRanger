"""Deterministic diagnostics rules engine. Implemented by Unit 3 (Diagnostics)."""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
from charset_normalizer import from_bytes

from .models import Diagnostic, Severity

_SAMPLE_BYTES = 65536
_CANDIDATE_DELIMITERS = (",", ";", "\t", "|")
_UTF8_FAMILY = frozenset({"utf_8", "utf8", "ascii", "us_ascii"})
_UNNAMED_PATTERN = re.compile(r"^Unnamed: \d+$")
_TEXT_SUFFIXES = frozenset({".csv", ".txt"})


def _normalize_encoding(name: str) -> str:
    return name.lower().replace("-", "_")


def detect_encoding(path: Path) -> tuple[str | None, float]:
    """Best-guess encoding and confidence via charset-normalizer (first ~64KB)."""
    try:
        with path.open("rb") as fh:
            sample = fh.read(_SAMPLE_BYTES)
    except OSError:
        return (None, 0.0)
    best = from_bytes(sample).best()
    if best is None:
        return (None, 0.0)
    confidence = min(max(1.0 - best.chaos, 0.0), 1.0)
    return (best.encoding, confidence)


def sniff_delimiter(path: Path, encoding: str = "utf-8") -> str | None:
    """csv.Sniffer over the first ~64KB; None if undetectable."""
    try:
        with path.open(encoding=encoding, errors="replace", newline="") as fh:
            sample = fh.read(_SAMPLE_BYTES)
    except OSError:
        return None
    if not sample.strip():
        return None
    first_line = sample.strip().splitlines()[0]
    try:
        sniffed = csv.Sniffer().sniff(sample, delimiters="".join(_CANDIDATE_DELIMITERS)).delimiter
        # Guard against Sniffer over-triggering (e.g. prose): the header must use it.
        if sniffed in first_line:
            return sniffed
    except csv.Error:
        pass
    # Fallback: count candidates in the sample and pick an unambiguous winner.
    counts = {d: sample.count(d) for d in _CANDIDATE_DELIMITERS}
    winner = max(counts, key=lambda d: counts[d])
    top = counts[winner]
    if top == 0 or sum(1 for c in counts.values() if c == top) > 1 or winner not in first_line:
        return None
    return winner


def _find_malformed_rows(path: Path, encoding: str, delimiter: str) -> tuple[list[int], int]:
    """1-based indices of rows whose field count differs from the header, plus that count.

    Streams the file; blank rows are skipped but keep their index. Returns ([], 0) when
    the file cannot be parsed as csv (e.g. a field exceeds the csv module's field limit).
    """
    expected = 0
    malformed: list[int] = []
    with path.open(encoding=encoding, errors="replace", newline="") as fh:
        try:
            for i, row in enumerate(csv.reader(fh, delimiter=delimiter), start=1):
                if not row:
                    continue
                if expected == 0:
                    expected = len(row)
                elif len(row) != expected:
                    malformed.append(i)
        except csv.Error:
            return ([], 0)
    return (malformed, expected)


def diagnose_file(path: Path, root: Path) -> tuple[list[Diagnostic], dict[str, Any]]:
    """Pre-read checks for text formats (csv/txt): encoding, delimiter, malformed-row
    detection (inconsistent field counts), empty file.

    Returns (diagnostics, reader_kwargs_hints), e.g. {"encoding": "latin-1", "sep": ";"}
    for the ingestor to pass to the reader.
    """
    rel = path.relative_to(root).as_posix()
    diagnostics: list[Diagnostic] = []
    hints: dict[str, Any] = {}

    if path.suffix.lower() not in _TEXT_SUFFIXES:
        return (diagnostics, hints)

    empty = Diagnostic(
        code="EMPTY_FILE",
        severity=Severity.ERROR,
        message="File is empty or contains only whitespace.",
        file=rel,
    )
    with path.open("rb") as fh:
        raw_sample = fh.read(_SAMPLE_BYTES)
    if len(raw_sample) < _SAMPLE_BYTES and not raw_sample.strip():
        diagnostics.append(empty)
        return (diagnostics, hints)

    encoding, confidence = detect_encoding(path)
    if encoding is None:
        diagnostics.append(
            Diagnostic(
                code="ENCODING_UNDETECTED",
                severity=Severity.ERROR,
                message="Could not detect the file encoding.",
                file=rel,
            )
        )
        return (diagnostics, hints)

    # Catch whitespace-only files whose encoding is not ASCII-compatible (e.g. UTF-16).
    decoded_sample = raw_sample.decode(encoding, errors="replace")
    if len(raw_sample) < _SAMPLE_BYTES and not decoded_sample.strip():
        diagnostics.append(empty)
        return (diagnostics, hints)

    if _normalize_encoding(encoding) not in _UTF8_FAMILY:
        diagnostics.append(
            Diagnostic(
                code="ENCODING_NON_UTF8",
                severity=Severity.WARNING,
                message=f"File is not UTF-8 encoded (detected {encoding}).",
                file=rel,
                detail={"encoding": encoding, "confidence": confidence},
            )
        )
        hints["encoding"] = encoding

    delimiter = sniff_delimiter(path, encoding=encoding)
    if delimiter is not None and delimiter != ",":
        diagnostics.append(
            Diagnostic(
                code="DELIMITER_SNIFFED",
                severity=Severity.INFO,
                message=f"Detected non-comma delimiter {delimiter!r}.",
                file=rel,
                detail={"delimiter": delimiter},
            )
        )
        hints["sep"] = delimiter

    malformed, expected = _find_malformed_rows(path, encoding, delimiter or ",")
    if malformed:
        diagnostics.append(
            Diagnostic(
                code="MALFORMED_ROWS",
                severity=Severity.WARNING,
                message=(
                    f"{len(malformed)} row(s) have a field count different from "
                    f"the header ({expected} fields expected)."
                ),
                file=rel,
                detail={"rows": malformed, "expected": expected},
            )
        )

    return (diagnostics, hints)


def diagnose_frame(df: pd.DataFrame, file_name: str) -> list[Diagnostic]:
    """Post-read schema checks: duplicate/empty column names, mixed-type object columns,
    all-null columns, constant columns."""
    diagnostics: list[Diagnostic] = []

    name_counts = Counter(str(c) for c in df.columns)
    for name, count in name_counts.items():
        if count > 1:
            diagnostics.append(
                Diagnostic(
                    code="DUPLICATE_COLUMN_NAMES",
                    severity=Severity.WARNING,
                    message=f"Column name {name!r} appears {count} times.",
                    file=file_name,
                    column=name,
                    detail={"count": count},
                )
            )

    for position, raw_name in enumerate(df.columns):
        name = str(raw_name)
        series = df.iloc[:, position]

        if not name.strip() or _UNNAMED_PATTERN.match(name):
            diagnostics.append(
                Diagnostic(
                    code="EMPTY_COLUMN_NAME",
                    severity=Severity.WARNING,
                    message=f"Column {position} has an empty or auto-generated name ({name!r}).",
                    file=file_name,
                    column=name,
                    detail={"position": position},
                )
            )

        non_null = series.dropna()
        if non_null.empty and not df.empty:
            diagnostics.append(
                Diagnostic(
                    code="ALL_NULL_COLUMN",
                    severity=Severity.WARNING,
                    message=f"Column {name!r} contains only null values.",
                    file=file_name,
                    column=name,
                )
            )
            continue

        if series.dtype == object:
            type_names = sorted({type(v).__name__ for v in non_null})
            if len(type_names) > 1:
                diagnostics.append(
                    Diagnostic(
                        code="MIXED_TYPE_COLUMN",
                        severity=Severity.WARNING,
                        message=f"Column {name!r} mixes value types: {', '.join(type_names)}.",
                        file=file_name,
                        column=name,
                        detail={"types": type_names},
                    )
                )

        try:
            distinct = non_null.nunique()
        except TypeError:  # unhashable values (e.g. lists from JSON cells)
            continue
        if len(df) > 1 and distinct == 1:
            diagnostics.append(
                Diagnostic(
                    code="CONSTANT_COLUMN",
                    severity=Severity.INFO,
                    message=f"Column {name!r} has a single distinct non-null value.",
                    file=file_name,
                    column=name,
                    detail={"value": str(non_null.iloc[0])},
                )
            )

    return diagnostics
