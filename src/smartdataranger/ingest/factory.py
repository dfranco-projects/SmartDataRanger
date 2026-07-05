"""Ingestor registry and directory orchestration. Implemented by Unit 1 (Ingestors)."""

from __future__ import annotations

import json
from pathlib import Path

from ..errors import UnsupportedFormatError
from ..models import Diagnostic, FileMetadata, Severity
from ..paths import WorkspacePaths
from ..readers import EXTENSION_TO_READER
from .base import Ingestor
from .ingestors import TabularIngestor, ZipIngestor


def get_ingestor(extension: str, *, extracted_dir: Path) -> Ingestor:
    """Registry lookup. Raises UnsupportedFormatError."""
    ext = extension.lower()
    if ext == ".zip":
        return ZipIngestor(extracted_dir=extracted_dir)
    if ext in EXTENSION_TO_READER:
        return TabularIngestor(ext)
    raise UnsupportedFormatError(f"Unsupported file type: {extension!r}")


def ingest_directory(
    paths: WorkspacePaths, *, write_metadata: bool = True
) -> tuple[list[FileMetadata], list[Diagnostic]]:
    """Scan paths.root (non-recursive, skip hidden/underscore files), route each file to
    its ingestor, extract zips into paths.extracted_dir, collect diagnostics for
    skipped/failed files, optionally write metadata.json.

    Never raises on a single bad file — records an INGESTION_FAILED diagnostic instead.
    """
    metadata: list[FileMetadata] = []
    diagnostics: list[Diagnostic] = []

    for entry in sorted(paths.root.iterdir()):
        if entry.name.startswith((".", "_")) or entry == paths.output_dir:
            continue
        if not entry.is_file():
            continue
        rel = entry.relative_to(paths.root).as_posix()
        extension = entry.suffix.lower()
        try:
            ingestor = get_ingestor(extension, extracted_dir=paths.extracted_dir)
        except UnsupportedFormatError:
            diagnostics.append(
                Diagnostic(
                    code="UNSUPPORTED_FILE_SKIPPED",
                    severity=Severity.INFO,
                    message=f"Unsupported file type {extension!r}; skipped.",
                    file=rel,
                )
            )
            continue
        try:
            metas, diags = ingestor.ingest(entry, paths.root)
        except Exception as exc:  # noqa: BLE001 - one bad file must never abort the run
            diagnostics.append(
                Diagnostic(
                    code="INGESTION_FAILED",
                    severity=Severity.ERROR,
                    message=f"Failed to ingest {rel}: {exc}",
                    file=rel,
                )
            )
            continue
        metadata.extend(metas)
        diagnostics.extend(diags)

    if write_metadata:
        paths.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps([meta.to_dict() for meta in metadata], indent=2)
        paths.metadata_file.write_text(payload, encoding="utf-8")

    return metadata, diagnostics
