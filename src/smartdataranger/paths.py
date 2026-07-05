"""Workspace path resolution. Implemented by Unit 2 (Paths + safe loader)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WorkspacePaths:
    root: Path  # the dataset directory the user pointed at
    output_dir: Path  # root / ".smartdataranger"
    metadata_file: Path  # output_dir / "metadata.json"
    extracted_dir: Path  # output_dir / "extracted"


def resolve_workspace(data_dir: str | Path) -> WorkspacePaths:
    """Validate data_dir exists and is a directory; return derived paths (no mkdir)."""
    raise NotImplementedError


def relative_source(path: Path, root: Path) -> str:
    """POSIX relative path of `path` under `root`."""
    raise NotImplementedError
