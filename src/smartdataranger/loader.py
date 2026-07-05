"""Metadata-driven DataFrame reconstruction. Implemented by Unit 2 (Paths + safe loader)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import readers
from .errors import MetadataError, UnsupportedFormatError
from .models import FileMetadata


def load_metadata(metadata_file: Path) -> list[FileMetadata]:
    """Parse metadata.json into FileMetadata records.

    Raises MetadataError if the file is missing, contains invalid JSON, the
    payload is not a list, or a record is missing required keys.
    """
    try:
        raw = metadata_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise MetadataError(f"Cannot read metadata file {metadata_file}: {exc}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MetadataError(f"Invalid JSON in metadata file {metadata_file}: {exc}") from exc
    if not isinstance(payload, list):
        raise MetadataError(
            f"Metadata file {metadata_file} must contain a JSON list, got {type(payload).__name__}"
        )
    records: list[FileMetadata] = []
    for i, item in enumerate(payload):
        if not isinstance(item, dict):
            raise MetadataError(
                f"Metadata record {i} in {metadata_file} must be an object, "
                f"got {type(item).__name__}"
            )
        try:
            records.append(FileMetadata.from_dict(item))
        except KeyError as exc:
            raise MetadataError(
                f"Metadata record {i} in {metadata_file} is missing required key {exc}"
            ) from exc
        except TypeError as exc:
            raise MetadataError(
                f"Metadata record {i} in {metadata_file} has a malformed field: {exc}"
            ) from exc
    return records


def load_dataframe(meta: FileMetadata, root: Path) -> pd.DataFrame:
    """Reconstruct one DataFrame via the whitelisted reader dispatch.

    Only READERS keys ever execute — this replaces the legacy
    ``eval(import_function)`` call. An unknown reader key (e.g. an injected
    ``"__import__('os').system"``) raises MetadataError: the metadata is what
    is malformed, so UnsupportedFormatError from readers.read_file is
    translated (chained) rather than propagated. Read failures propagate as
    IngestionError from readers.read_file. A source that resolves outside
    root (absolute path or ``..`` traversal) raises MetadataError.
    """
    target = (root / meta.source).resolve()
    if not target.is_relative_to(root.resolve()):
        raise MetadataError(
            f"Metadata for {meta.file_name!r} has source {meta.source!r} outside the dataset root"
        )
    try:
        return readers.read_file(target, meta.reader, **meta.reader_kwargs)
    except UnsupportedFormatError as exc:
        raise MetadataError(
            f"Metadata for {meta.file_name!r} references unknown reader {meta.reader!r}"
        ) from exc


def load_dataset(metadata_file: Path, root: Path | None = None) -> dict[str, pd.DataFrame]:
    """Load all files described by metadata_file; keys are file_name.

    root defaults to metadata_file.parent.parent, since the metadata lives in
    <root>/.smartdataranger/metadata.json.
    """
    if root is None:
        root = metadata_file.parent.parent
    return {meta.file_name: load_dataframe(meta, root) for meta in load_metadata(metadata_file)}
