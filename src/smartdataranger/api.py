"""Flagship one-call API. Implemented by Unit 5 (import_dataset API)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .models import ImportReport


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
    raise NotImplementedError
