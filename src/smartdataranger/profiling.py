"""Per-column data-quality profiling. Implemented by Unit 4 (Profiling)."""

from __future__ import annotations

import pandas as pd

from .models import ColumnProfile


def profile_columns(df: pd.DataFrame) -> list[ColumnProfile]:
    """One ColumnProfile per column."""
    raise NotImplementedError


def count_duplicate_rows(df: pd.DataFrame) -> int:
    """Number of fully-duplicated rows."""
    raise NotImplementedError
