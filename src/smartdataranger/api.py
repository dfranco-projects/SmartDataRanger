"""Flagship one-call API. Implemented by Unit 5 (import_dataset API)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .diagnostics import diagnose_frame
from .errors import IngestionError, MetadataError
from .ingest.factory import ingest_directory
from .loader import load_dataframe
from .models import Diagnostic, FileReport, ImportReport, Severity
from .paths import resolve_workspace
from .profiling import count_duplicate_rows, profile_columns


def import_dataset(
    path: str | Path,
    *,
    profile: bool = True,
    write_metadata: bool = True,
) -> tuple[pd.DataFrame | dict[str, pd.DataFrame], ImportReport]:
    """Ingest a folder (or single file), load DataFrames, run diagnostics + profiling.

    Returns (df_or_dict, ImportReport). A single data file yields a bare DataFrame;
    multiple files yield {file_name: df}; an empty folder yields ({}, report) with a
    dataset-level EMPTY_DATASET diagnostic.
    """
    target = Path(path)
    only_source: str | None = None
    if target.is_file():
        only_source = target.name
        workspace_dir = target.parent
    else:
        workspace_dir = target

    paths = resolve_workspace(workspace_dir)
    metadata, dataset_diagnostics = ingest_directory(paths, write_metadata=write_metadata)
    dataset_diagnostics = list(dataset_diagnostics)
    if only_source is not None:
        metadata = [m for m in metadata if m.source == only_source]
        dataset_diagnostics = [d for d in dataset_diagnostics if d.file in ("", only_source)]

    frames: dict[str, pd.DataFrame] = {}
    file_reports: list[FileReport] = []
    for meta in metadata:
        file_report = FileReport(metadata=meta)
        file_reports.append(file_report)
        try:
            df = load_dataframe(meta, paths.root)
        except (IngestionError, MetadataError) as exc:
            file_report.diagnostics.append(
                Diagnostic(
                    code="INGESTION_FAILED",
                    severity=Severity.ERROR,
                    message=f"Failed to load {meta.file_name}: {exc}",
                    file=meta.file_name,
                )
            )
            continue
        frames[meta.file_name] = df
        if profile:
            file_report.diagnostics.extend(diagnose_frame(df, meta.file_name))
            file_report.column_profiles = profile_columns(df)
            duplicates = count_duplicate_rows(df)
            file_report.duplicate_row_count = duplicates
            if duplicates > 0:
                file_report.diagnostics.append(
                    Diagnostic(
                        code="DUPLICATE_ROWS",
                        severity=Severity.INFO,
                        message=f"{meta.file_name} has {duplicates} fully duplicated row(s)",
                        file=meta.file_name,
                        detail={"duplicate_row_count": duplicates},
                    )
                )

    if not metadata:
        dataset_diagnostics.append(
            Diagnostic(
                code="EMPTY_DATASET",
                severity=Severity.WARNING,
                message=f"No importable data files found in {paths.root}",
                file="",
            )
        )

    report = ImportReport(root=paths.root, files=file_reports, diagnostics=dataset_diagnostics)
    if len(frames) == 1:
        return next(iter(frames.values())), report
    return frames, report
