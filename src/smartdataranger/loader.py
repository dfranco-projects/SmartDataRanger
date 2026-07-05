"""Metadata-driven DataFrame reconstruction. Implemented by Unit 2 (Paths + safe loader)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .models import FileMetadata


def load_metadata(metadata_file: Path) -> list[FileMetadata]:
    """Parse metadata.json into FileMetadata records. Raises MetadataError."""
    raise NotImplementedError


def load_dataframe(meta: FileMetadata, root: Path) -> pd.DataFrame:
    """Reconstruct one DataFrame via readers.read_file(root / meta.source, meta.reader,
    **meta.reader_kwargs)."""
    raise NotImplementedError


def load_dataset(metadata_file: Path, root: Path | None = None) -> dict[str, pd.DataFrame]:
    """Load all files; keys are file_name. root defaults to metadata_file.parent.parent."""
    raise NotImplementedError
