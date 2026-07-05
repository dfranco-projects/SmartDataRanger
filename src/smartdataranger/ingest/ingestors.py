"""Concrete ingestors. Implemented by Unit 1 (Ingestors modernization).

TabularIngestor covers csv/xlsx/xls/parquet/json/txt through the whitelisted
readers registry; ZipIngestor extracts archives into the workspace
extracted_dir (with zip-slip protection) and ingests the supported members.
"""

from __future__ import annotations

import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from ..diagnostics import diagnose_file
from ..errors import IngestionError
from ..models import Diagnostic, FileMetadata, Severity
from ..readers import EXTENSION_TO_READER, read_file, reader_for_extension

_TEXT_READERS = frozenset({"csv", "txt"})


def _diagnose(path: Path, root: Path) -> tuple[list[Diagnostic], dict[str, Any]]:
    """Call the diagnostics stub, tolerating it not being implemented yet."""
    try:
        diags, hints = diagnose_file(path, root)
    except NotImplementedError:
        return [], {}
    return list(diags), dict(hints)


class TabularIngestor:
    """Ingest one flat tabular file of a given extension via the readers registry."""

    def __init__(self, extension: str) -> None:
        self.extension = extension.lower()
        self.reader = reader_for_extension(self.extension)  # raises UnsupportedFormatError

    def ingest(self, file_path: Path, root: Path) -> tuple[list[FileMetadata], list[Diagnostic]]:
        diagnostics: list[Diagnostic] = []
        reader_kwargs: dict[str, Any] = {}
        if self.reader.key in _TEXT_READERS:
            diagnostics, hints = _diagnose(file_path, root)
            reader_kwargs.update(hints)
        df = read_file(file_path, self.reader.key, **reader_kwargs)
        meta = FileMetadata(
            file_name=file_path.name,
            file_type=self.extension,
            reader=self.reader.key,
            reader_kwargs=reader_kwargs,
            columns=[str(c) for c in df.columns],
            row_count=len(df),
            source=file_path.relative_to(root).as_posix(),
        )
        return [meta], diagnostics


class ZipIngestor:
    """Extract a zip archive into `extracted_dir` and ingest its supported members."""

    def __init__(self, extracted_dir: Path) -> None:
        self.extracted_dir = extracted_dir

    def ingest(self, file_path: Path, root: Path) -> tuple[list[FileMetadata], list[Diagnostic]]:
        self.extracted_dir.mkdir(parents=True, exist_ok=True)
        base = self.extracted_dir.resolve()
        try:
            with zipfile.ZipFile(file_path) as zf:
                members = [n for n in zf.namelist() if not n.endswith("/")]
                for name in members:
                    target = (base / name).resolve()
                    if not target.is_relative_to(base):
                        raise IngestionError(
                            f"Zip member {name!r} in {file_path.name} resolves outside "
                            "the extraction directory (zip-slip)"
                        )
                zf.extractall(base)
        except zipfile.BadZipFile as exc:
            raise IngestionError(f"Failed to extract {file_path.name}: {exc}") from exc

        metadata: list[FileMetadata] = []
        diagnostics: list[Diagnostic] = []
        for name in members:
            if PurePosixPath(name).name.startswith((".", "_")):
                continue
            extracted = self.extracted_dir / name
            extension = extracted.suffix.lower()
            member_rel = extracted.relative_to(root).as_posix()
            if extension not in EXTENSION_TO_READER:
                diagnostics.append(
                    Diagnostic(
                        code="UNSUPPORTED_FILE_SKIPPED",
                        severity=Severity.INFO,
                        message=f"Unsupported file type {extension!r}; skipped.",
                        file=member_rel,
                    )
                )
                continue
            try:
                metas, diags = TabularIngestor(extension).ingest(extracted, root)
            except Exception as exc:  # noqa: BLE001 - one bad member must not fail the archive
                diagnostics.append(
                    Diagnostic(
                        code="INGESTION_FAILED",
                        severity=Severity.ERROR,
                        message=str(exc),
                        file=member_rel,
                    )
                )
                continue
            metadata.extend(metas)
            diagnostics.extend(diags)
        return metadata, diagnostics
