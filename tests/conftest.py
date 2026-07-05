"""Shared test fixtures. This module is FINAL: work units must not edit it.

Every fixture generates tiny sample files into tmp_path and returns the file path.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd
import pytest

_FRAME = pd.DataFrame(
    {
        "id": [1, 2, 3, 3],
        "name": ["ada", "grace", "alan", "alan"],
        "score": [9.5, None, 7.0, 7.0],
    }
)


@pytest.fixture
def sample_frame() -> pd.DataFrame:
    return _FRAME.copy()


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    path = tmp_path / "sample.csv"
    _FRAME.to_csv(path, index=False)
    return path


@pytest.fixture
def sample_txt(tmp_path: Path) -> Path:
    path = tmp_path / "sample.txt"
    _FRAME.to_csv(path, index=False, sep="\t")
    return path


@pytest.fixture
def sample_json(tmp_path: Path) -> Path:
    path = tmp_path / "sample.json"
    _FRAME.to_json(path, orient="records")
    return path


@pytest.fixture
def sample_xlsx(tmp_path: Path) -> Path:
    path = tmp_path / "sample.xlsx"
    _FRAME.to_excel(path, index=False)
    return path


@pytest.fixture
def sample_parquet(tmp_path: Path) -> Path:
    path = tmp_path / "sample.parquet"
    _FRAME.to_parquet(path, index=False)
    return path


@pytest.fixture
def sample_zip(tmp_path: Path) -> Path:
    """Zip archive containing two CSV members."""
    inner_a = tmp_path / "inner_a.csv"
    inner_b = tmp_path / "inner_b.csv"
    _FRAME.to_csv(inner_a, index=False)
    _FRAME.head(2).to_csv(inner_b, index=False)
    path = tmp_path / "sample.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.write(inner_a, "inner_a.csv")
        zf.write(inner_b, "inner_b.csv")
    inner_a.unlink()
    inner_b.unlink()
    return path


@pytest.fixture
def messy_csv(tmp_path: Path) -> Path:
    """Latin-1 encoded, semicolon-delimited, with one short (malformed) row."""
    path = tmp_path / "messy.csv"
    content = (
        "ciudad;país;población\n"
        "Bogotá;Colombia;8000000\n"
        "São Paulo;Brasil\n"
        "México DF;México;9000000\n"
    )
    path.write_bytes(content.encode("latin-1"))
    return path
