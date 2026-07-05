"""Per-column data-quality profiling. Implemented by Unit 4 (Profiling)."""

from __future__ import annotations

import pandas as pd

from .models import ColumnProfile

_SAMPLE_SIZE = 5


def profile_columns(df: pd.DataFrame) -> list[ColumnProfile]:
    """One ColumnProfile per column."""
    profiles: list[ColumnProfile] = []
    row_count = len(df)
    # Iterate positionally so duplicate column names still yield one Series each.
    for i, name in enumerate(df.columns):
        series = df.iloc[:, i]
        null_count = int(series.isna().sum())
        non_null_count = row_count - null_count
        non_null = series.dropna()
        try:
            unique_count = int(non_null.nunique())
            sample_values = [str(v) for v in non_null.unique()[:_SAMPLE_SIZE]]
        except TypeError:
            # Unhashable cell values (e.g. lists): compare by repr instead.
            unique_count = int(non_null.map(repr).nunique())
            sample_values = [str(v) for v in non_null.head(_SAMPLE_SIZE)]
        null_pct = round(null_count / row_count * 100, 2) if row_count else 0.0
        cardinality_pct = round(unique_count / non_null_count * 100, 2) if non_null_count else 0.0
        profiles.append(
            ColumnProfile(
                name=str(name),
                dtype=str(series.dtype),
                non_null_count=non_null_count,
                null_count=null_count,
                null_pct=null_pct,
                unique_count=unique_count,
                cardinality_pct=cardinality_pct,
                sample_values=sample_values,
            )
        )
    return profiles


def count_duplicate_rows(df: pd.DataFrame) -> int:
    """Number of fully-duplicated rows."""
    try:
        return int(df.duplicated().sum())
    except TypeError:
        # Unhashable cell values (e.g. lists): compare rows by repr instead.
        safe = pd.DataFrame({i: df.iloc[:, i].map(repr) for i in range(df.shape[1])})
        return int(safe.duplicated().sum())
