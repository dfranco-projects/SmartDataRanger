"""Data contracts shared by every SmartDataRanger module.

This module is FINAL: work units implement against these types and must not edit them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One finding from the rules engine.

    Codes in use: ENCODING_NON_UTF8, ENCODING_UNDETECTED, DELIMITER_SNIFFED,
    MALFORMED_ROWS, EMPTY_FILE, DUPLICATE_COLUMN_NAMES, EMPTY_COLUMN_NAME,
    MIXED_TYPE_COLUMN, ALL_NULL_COLUMN, CONSTANT_COLUMN, DUPLICATE_ROWS,
    UNSUPPORTED_FILE_SKIPPED, INGESTION_FAILED, EMPTY_DATASET.
    """

    code: str
    severity: Severity
    message: str
    file: str  # file name relative to the dataset root; "" for dataset-level findings
    column: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ColumnProfile:
    """Per-column data-quality profile."""

    name: str
    dtype: str  # str(df[col].dtype)
    non_null_count: int
    null_count: int
    null_pct: float  # 0.0-100.0
    unique_count: int
    cardinality_pct: float  # unique / non_null * 100 (0.0 if no non-null values)
    sample_values: list[str]  # up to 5 stringified non-null examples


@dataclass(frozen=True, slots=True)
class FileMetadata:
    """Reproducible import recipe for one file."""

    file_name: str  # e.g. "sales.csv"
    file_type: str  # extension with dot, e.g. ".csv"
    reader: str  # key into readers.READERS, e.g. "csv"
    reader_kwargs: dict[str, Any]  # extra kwargs; never contains the path (that is `source`)
    columns: list[str]
    row_count: int
    source: str  # POSIX path relative to the dataset root

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileMetadata:
        return cls(
            file_name=data["file_name"],
            file_type=data["file_type"],
            reader=data["reader"],
            reader_kwargs=dict(data.get("reader_kwargs", {})),
            columns=list(data["columns"]),
            row_count=data["row_count"],
            source=data["source"],
        )


@dataclass(slots=True)
class FileReport:
    metadata: FileMetadata
    diagnostics: list[Diagnostic] = field(default_factory=list)
    column_profiles: list[ColumnProfile] = field(default_factory=list)
    duplicate_row_count: int = 0


@dataclass(slots=True)
class ImportReport:
    root: Path
    files: list[FileReport] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)  # dataset-level

    @property
    def all_diagnostics(self) -> list[Diagnostic]:
        """Dataset-level plus per-file diagnostics, in order."""
        out = list(self.diagnostics)
        for f in self.files:
            out.extend(f.diagnostics)
        return out

    def has_errors(self) -> bool:
        return any(d.severity is Severity.ERROR for d in self.all_diagnostics)

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable form (used by `ranger --json`)."""
        return {
            "root": str(self.root),
            "diagnostics": [asdict(d) for d in self.diagnostics],
            "files": [
                {
                    "metadata": f.metadata.to_dict(),
                    "diagnostics": [asdict(d) for d in f.diagnostics],
                    "column_profiles": [asdict(p) for p in f.column_profiles],
                    "duplicate_row_count": f.duplicate_row_count,
                }
                for f in self.files
            ],
        }
