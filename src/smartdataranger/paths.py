"""Workspace path resolution. Implemented by Unit 2 (Paths + safe loader)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import SmartDataRangerError


@dataclass(frozen=True, slots=True)
class WorkspacePaths:
    root: Path  # the dataset directory the user pointed at
    output_dir: Path  # root / ".smartdataranger"
    metadata_file: Path  # output_dir / "metadata.json"
    extracted_dir: Path  # output_dir / "extracted"


def resolve_workspace(data_dir: str | Path) -> WorkspacePaths:
    """Validate data_dir exists and is a directory; return derived paths (no mkdir).

    The path is user-expanded (``~``) and fully resolved so downstream code never
    depends on the current working directory.

    Raises SmartDataRangerError if data_dir does not exist or is not a directory.
    (The base error is used rather than IngestionError because no file ingestion
    is involved — the workspace itself is invalid.)
    """
    root = Path(data_dir).expanduser().resolve()
    if not root.exists():
        raise SmartDataRangerError(f"Data directory does not exist: {root}")
    if not root.is_dir():
        raise SmartDataRangerError(f"Data directory is not a directory: {root}")
    output_dir = root / ".smartdataranger"
    return WorkspacePaths(
        root=root,
        output_dir=output_dir,
        metadata_file=output_dir / "metadata.json",
        extracted_dir=output_dir / "extracted",
    )


def relative_source(path: Path, root: Path) -> str:
    """POSIX relative path of `path` under `root`.

    Both paths are resolved before comparison. Raises SmartDataRangerError if
    `path` is not located under `root`.
    """
    resolved_path = path.expanduser().resolve()
    resolved_root = root.expanduser().resolve()
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError as exc:
        raise SmartDataRangerError(
            f"Path {resolved_path} is not under root {resolved_root}"
        ) from exc
