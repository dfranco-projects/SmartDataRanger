"""Safe, whitelisted reader dispatch — the replacement for the legacy eval() call.

This module is FINAL: work units use it as-is and must not edit it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from .errors import IngestionError, UnsupportedFormatError

ReaderFunc = Callable[..., pd.DataFrame]


@dataclass(frozen=True, slots=True)
class Reader:
    key: str
    func: ReaderFunc
    default_kwargs: dict[str, Any] = field(default_factory=dict)


READERS: dict[str, Reader] = {
    "csv": Reader("csv", pd.read_csv),
    "excel": Reader("excel", pd.read_excel),
    "parquet": Reader("parquet", pd.read_parquet),
    "json": Reader("json", pd.read_json),
    "txt": Reader("txt", pd.read_csv, {"sep": "\t"}),
}

EXTENSION_TO_READER: dict[str, str] = {
    ".csv": "csv",
    ".xlsx": "excel",
    ".xls": "excel",
    ".parquet": "parquet",
    ".json": "json",
    ".txt": "txt",
}

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(EXTENSION_TO_READER) | {".zip"}


def reader_for_extension(extension: str) -> Reader:
    """Look up the Reader for a file extension (e.g. ".csv").

    Raises UnsupportedFormatError for unknown extensions.
    """
    key = EXTENSION_TO_READER.get(extension.lower())
    if key is None:
        raise UnsupportedFormatError(f"No reader registered for extension {extension!r}")
    return READERS[key]


def read_file(path: Path, reader: str, **kwargs: Any) -> pd.DataFrame:
    """Read `path` with the whitelisted reader `reader` (a READERS key).

    kwargs override the reader's default_kwargs. The first positional argument
    is always the path — no eval, no dynamic attribute lookup.

    Raises UnsupportedFormatError for unknown reader keys and IngestionError
    wrapping any underlying read failure.
    """
    spec = READERS.get(reader)
    if spec is None:
        raise UnsupportedFormatError(f"Unknown reader key {reader!r}")
    merged = {**spec.default_kwargs, **kwargs}
    try:
        return spec.func(path, **merged)
    except Exception as exc:
        raise IngestionError(f"Failed to read {path} with reader {reader!r}: {exc}") from exc
