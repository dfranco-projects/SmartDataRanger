"""Ingestor registry and directory orchestration. Implemented by Unit 1 (Ingestors)."""

from __future__ import annotations

from pathlib import Path

from ..models import Diagnostic, FileMetadata
from ..paths import WorkspacePaths
from .base import Ingestor


def get_ingestor(extension: str, *, extracted_dir: Path) -> Ingestor:
    """Registry lookup. Raises UnsupportedFormatError."""
    raise NotImplementedError


def ingest_directory(
    paths: WorkspacePaths, *, write_metadata: bool = True
) -> tuple[list[FileMetadata], list[Diagnostic]]:
    """Scan paths.root (non-recursive, skip hidden/underscore files), route each file to
    its ingestor, extract zips into paths.extracted_dir, collect diagnostics for
    skipped/failed files, optionally write metadata.json.

    Never raises on a single bad file — records an INGESTION_FAILED diagnostic instead.
    """
    raise NotImplementedError
