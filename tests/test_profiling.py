"""Tests for smartdataranger.profiling."""

from __future__ import annotations

import pandas as pd

from smartdataranger.models import ColumnProfile
from smartdataranger.profiling import count_duplicate_rows, profile_columns


def _by_name(profiles: list[ColumnProfile]) -> dict[str, ColumnProfile]:
    return {p.name: p for p in profiles}


def test_sample_frame_profiles(sample_frame: pd.DataFrame) -> None:
    profiles = profile_columns(sample_frame)
    assert [p.name for p in profiles] == ["id", "name", "score"]
    by_name = _by_name(profiles)

    id_profile = by_name["id"]
    assert id_profile.dtype == str(sample_frame["id"].dtype)
    assert id_profile.non_null_count == 4
    assert id_profile.null_count == 0
    assert id_profile.null_pct == 0.0
    assert id_profile.unique_count == 3
    assert id_profile.cardinality_pct == 75.0
    assert id_profile.sample_values == ["1", "2", "3"]

    name_profile = by_name["name"]
    assert name_profile.non_null_count == 4
    assert name_profile.null_count == 0
    assert name_profile.unique_count == 3  # 'alan' appears twice
    assert name_profile.cardinality_pct == 75.0
    assert name_profile.sample_values == ["ada", "grace", "alan"]

    score_profile = by_name["score"]
    assert score_profile.non_null_count == 3
    assert score_profile.null_count == 1
    assert score_profile.null_pct == 25.0
    assert score_profile.unique_count == 2
    assert score_profile.cardinality_pct == 66.67
    assert score_profile.sample_values == ["9.5", "7.0"]


def test_sample_frame_duplicate_rows(sample_frame: pd.DataFrame) -> None:
    assert count_duplicate_rows(sample_frame) == 1


def test_empty_frame_no_columns() -> None:
    assert profile_columns(pd.DataFrame()) == []
    assert count_duplicate_rows(pd.DataFrame()) == 0


def test_empty_frame_with_columns() -> None:
    df = pd.DataFrame({"a": pd.Series(dtype="int64"), "b": pd.Series(dtype="object")})
    profiles = profile_columns(df)
    assert len(profiles) == 2
    for profile in profiles:
        assert profile.non_null_count == 0
        assert profile.null_count == 0
        assert profile.null_pct == 0.0
        assert profile.unique_count == 0
        assert profile.cardinality_pct == 0.0
        assert profile.sample_values == []
    assert count_duplicate_rows(df) == 0


def test_all_null_column() -> None:
    df = pd.DataFrame({"empty": [None, None, None]})
    (profile,) = profile_columns(df)
    assert profile.non_null_count == 0
    assert profile.null_count == 3
    assert profile.null_pct == 100.0
    assert profile.unique_count == 0
    assert profile.cardinality_pct == 0.0
    assert profile.sample_values == []


def test_duplicate_column_names() -> None:
    df = pd.DataFrame([[1, "x"], [2, "y"]])
    df.columns = ["col", "col"]
    profiles = profile_columns(df)
    assert [p.name for p in profiles] == ["col", "col"]
    assert profiles[0].sample_values == ["1", "2"]
    assert profiles[1].sample_values == ["x", "y"]
    assert profiles[0].unique_count == 2
    assert profiles[1].unique_count == 2


def test_unhashable_values_do_not_crash() -> None:
    df = pd.DataFrame({"tags": [[1, 2], [1, 2], [3], None]})
    (profile,) = profile_columns(df)
    assert profile.non_null_count == 3
    assert profile.null_count == 1
    assert profile.null_pct == 25.0
    assert profile.unique_count == 2  # [1, 2] appears twice
    assert profile.cardinality_pct == 66.67
    assert profile.sample_values == ["[1, 2]", "[1, 2]", "[3]"]


def test_unhashable_values_duplicate_rows() -> None:
    df = pd.DataFrame({"tags": [[1, 2], [1, 2], [3]], "n": [1, 1, 2]})
    assert count_duplicate_rows(df) == 1


def test_sample_values_capped_at_five_and_stringified() -> None:
    df = pd.DataFrame({"n": list(range(10))})
    (profile,) = profile_columns(df)
    assert profile.unique_count == 10
    assert profile.cardinality_pct == 100.0
    assert profile.sample_values == ["0", "1", "2", "3", "4"]
    assert all(isinstance(v, str) for v in profile.sample_values)
