"""Deterministic diagnostics rules engine. Implemented by Unit 3 (Diagnostics)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .models import Diagnostic


def detect_encoding(path: Path) -> tuple[str | None, float]:
    """Best-guess encoding and confidence via charset-normalizer."""
    raise NotImplementedError


def sniff_delimiter(path: Path, encoding: str = "utf-8") -> str | None:
    """csv.Sniffer over the first ~64KB; None if undetectable."""
    raise NotImplementedError


def diagnose_file(path: Path, root: Path) -> tuple[list[Diagnostic], dict[str, Any]]:
    """Pre-read checks for text formats (csv/txt): encoding, delimiter, malformed-row
    detection (inconsistent field counts), empty file.

    Returns (diagnostics, reader_kwargs_hints), e.g. {"encoding": "latin-1", "sep": ";"}
    for the ingestor to pass to the reader.
    """
    raise NotImplementedError


def diagnose_frame(df: pd.DataFrame, file_name: str) -> list[Diagnostic]:
    """Post-read schema checks: duplicate/empty column names, mixed-type object columns,
    all-null columns, constant columns."""
    raise NotImplementedError
