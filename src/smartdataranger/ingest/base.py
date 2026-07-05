"""Ingestor protocol. This module is FINAL: work units implement against it."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from ..models import Diagnostic, FileMetadata


@runtime_checkable
class Ingestor(Protocol):
    """One ingestor per format family.

    Returns metadata for 1..n files (zip yields many) plus any diagnostics raised
    during ingestion.
    """

    def ingest(
        self, file_path: Path, root: Path
    ) -> tuple[list[FileMetadata], list[Diagnostic]]: ...
